import sys
import pika
import signal
import logging
from random import randint


class Receiver(object):

    """
    RabbitMQ receiver that handles unexpected interactions
    with RabbitMQ such as channel and connection closures.

    If RabbitMQ closes the connection, it will reopen it. 

    If the channel is closed, it will indicate a problem with one of the
    commands that were issued and that should surface in the output as well.
    """

    def __init__(self, consumer_callback, amqp_url, exchange, **kwargs):
        """Create a new instance of the Receiver class, passing in the various
        parameters used to connect to RabbitMQ.

        Other than consumer_callback, amqp_url, exchange the optional arguments are: 
        exchange_type, queue, binding_keys, queue_exclusive, queue_durable, no_ack

        :param method consumer_callback: The method to callback when consuming (messages)
            with the signature consumer_callback(channel, method, properties, body), where
                                channel: pika.Channel
                                method: pika.spec.Basic.Deliver
                                properties: pika.spec.BasicProperties
                                body: str, unicode, or bytes (python 3.x)
        :param str amqp_url: The AMQP url to connect with
        :param str exchange: Name of exchange
        :param str exchange_type: The exchange type to use. If no vaue is given for exchange 
                type, it will assume that the exchange already exists and will use the existing 
                exchange.
        :param str queue: Name of the queue. Its default value is ''. When the queue name is
                empty string i.e. '', server chooses a random queue name for us.
        :param list binding_keys: The list of binding keys to be used. It's a list of strings. 
                It's default value is [None]
        :param bool queue_exclusive: Only allow access by the current connection. This is
                is the exclusive flag used in queue_declare() function of pika channel.
                If the flag is true, consumer queue is deleted on disconnection. It's default
                value is False. If server is going to choose a name for queue we set this variable 
                True irrespective of what value user has given for queue_exclusive
        :param bool queue_durable: Survive reboots of the broker. This is the durable flag 
                used in queue_declare() function of pika channel. If this flag is True, messages 
                in queue are saved on disk in case RabbitMQ quits or crashes. It's default value 
                is True
        :param bool no_ack: Tell the broker to not expect a response (acknowledgement). It's 
                default value is False
        :param bool safe_stop: If this option is True, system will try to gracefully stop the 
                connection if the process is killed (with SIGTERM signal). Its default value is True

        """
        self._connection = None
        self._channel = None
        self._closing = False
        self._consumer_tag = None
        self._LOGGER = logging.getLogger(__name__)
        self.consumer_callback = consumer_callback
        self._url = amqp_url
        self.exchange = exchange
        self.parse_input_args(kwargs)

    def parse_input_args(self, kwargs):
        """Parse and set connection parameters from a dictionary.

        Assigns defaults for missing parameters.
        """
        self.exchange_type = kwargs.get('exchange_type')
        self.queue = kwargs.get('queue', '')
        self.binding_keys = kwargs.get('binding_keys', [None])
        self.queue_exclusive = kwargs.get('queue_exclusive', False)
        self.queue_durable = kwargs.get('queue_durable', True)
        self.no_ack = kwargs.get('no_ack', False)
        self.safe_stop = kwargs.get('safe_stop', True)

        # if queue name is empty string server will choose a random queue name
        # and we want this queue to be deleted when connection closes, hence
        # setting queue_exclusive True
        if not self.queue:
            self.queue_exclusive = True

    def connect(self):
        """Connect to RabbitMQ, returning the connection handle.

        When the connection is established, the on_connection_open method
        will be invoked by pika.

        :rtype: pika.SelectConnection

        """
        self._LOGGER.info('Connecting to %s with queue %s and exchange %s', self._url, self.queue, self.exchange)
        return pika.SelectConnection(pika.URLParameters(self._url),
                                     self.on_connection_open,
                                     self.on_connection_error,
                                     stop_ioloop_on_close=False)

    def on_connection_open(self, unused_connection):
        """Invoked by pika once the connection to RabbitMQ has
        been established.

        It passes the handle to the connection object in
        case we need it, but in this case, we'll just mark it unused.

        :type unused_connection: pika.SelectConnection

        """
        self._LOGGER.info('Connection opened for queue %s', self.queue)
        self.add_on_connection_close_callback()
        self.open_channel()

    def add_on_connection_close_callback(self):
        """Add a callback that will be invoked if RabbitMQ closes the connection
        for some reason. If RabbitMQ does close the connection, on_connection_closed
        will be invoked by pika.

        """
        self._LOGGER.info('Adding connection close callback')
        self._connection.add_on_close_callback(self.on_connection_closed)

   


    def on_connection_error(self, connection, error):
        self._LOGGER.warning("Connection failed.Retrying in next 5 seconds for queue %s", self.queue)
        connection.add_timeout(5, self.reconnect)

    def on_connection_closed(self, connection, reply_code, reply_text):
        """Invoked by pika when the connection to RabbitMQ is closed unexpectedly.

        Since it is unexpected, we will reconnect to RabbitMQ if it disconnects.

        :param pika.connection.Connection connection: The closed connection obj
        :param int reply_code: The server provided reply_code if given
        :param str reply_text: The server provided reply_text if given

        """
        self._channel = None
        if self._closing:
            self._connection.ioloop.stop()
        else:
            self._LOGGER.warning('Connection closed, reopening in 5 seconds: (%s) %s',
                                 reply_code, reply_text)
            self._connection.add_timeout(5, self.reconnect)

    def reconnect(self):
        """Invoked by the IOLoop timer if the connection is
        closed.

        See the on_connection_closed method.

        """
        # This is the old connection IOLoop instance, stop its ioloop
        self._connection.ioloop.stop()

        if not self._closing:
            # Create a new connection
            self._connection = self.connect()
            # There is now a new connection, needs a new ioloop to run
            self._connection.ioloop.start()

    def open_channel(self):
        """Open a new channel with RabbitMQ by issuing the Channel.Open RPC
        command.

        When RabbitMQ responds that the channel is open, the
        on_channel_open callback will be invoked by pika.

        """
        self._LOGGER.info('Creating a new channel')
        self._connection.channel(on_open_callback=self.on_channel_open)

    def on_channel_open(self, channel):
        """Invoked by pika when the channel has been opened.
        The channel object is passed in so we can make use of it.

        Since the channel is now open, we'll declare the exchange to use.

        :param pika.channel.Channel channel: The channel object

        """
        self._LOGGER.info('Channel opened')
        self._channel = channel
        self.add_on_channel_close_callback()
        if self.exchange_type:
            self.setup_exchange(self.exchange)
        else:
            self._LOGGER.info(
                'Skipped exchange setup assuming that exchange already exists')
            self.setup_queue(self.queue)

    def add_on_channel_close_callback(self):
        """Add a callback that will be invoked if RabbitMQ closes the channel
        for some reason.

        If RabbitMQ does close the channel, on_channel_closed  will be invoked
        by pika.

        """
        self._LOGGER.info('Adding channel close callback')
        self._channel.add_on_close_callback(self.on_channel_closed)

    def on_channel_closed(self, channel, reply_code, reply_text):
        """Invoked by pika when RabbitMQ unexpectedly closes the channel.

        Channels are usually closed if we attempt to do something that
        violates the protocol, such as re-declare an exchange or queue with
        different parameters. In this case, we'll close the connection
        to shutdown the object.

        :param pika.channel.Channel: The closed channel
        :param int reply_code: The numeric reason the channel was closed
        :param str reply_text: The text reason the channel was closed

        """
        self._LOGGER.warning('Channel %i was closed: (%s) %s',
                             channel, reply_code, reply_text)
        self._connection.close()

    def setup_exchange(self, exchange_name):
        """Setup the exchange on RabbitMQ by invoking the Exchange.Declare RPC
        command.

        When it is complete, the on_exchange_declareok method will be invoked by pika.

        :param str|unicode exchange_name: The name of the exchange to declare

        """
        self._LOGGER.info('Declaring exchange %s', exchange_name)
        self._channel.exchange_declare(self.on_exchange_declareok,
                                       exchange_name,
                                       self.exchange_type)

    def on_exchange_declareok(self, unused_frame):
        """Invoked by pika when RabbitMQ has finished the Exchange.Declare RPC
        command.

        :param pika.Frame.Method unused_frame: Exchange.DeclareOk response frame

        """
        self._LOGGER.info('Exchange declared')
        self.setup_queue(self.queue)

    def setup_queue(self, queue_name):
        """Setup the queue on RabbitMQ by invoking the Queue.Declare RPC
        command.

        When it is complete, the on_queue_declareok method will be invoked by pika.

        Please note that if there already exist a queue with the queue name you 
        have given but different parameters (i.e. queue_durable, queue_exclusive 
        etc.), then you will have to delete the earlier queue first else it won't
        work. It won't be any problem if queue parameters are also same along with 
        the name        

        :param str|unicode queue_name: The name of the queue to declare.

        """
        if queue_name == '':
            self._LOGGER.info('Declaring queue with server defined queue name')
        else:
            self._LOGGER.info('Declaring queue %s', queue_name)
        self._channel.queue_declare(self.on_queue_declareok, queue=queue_name,
                                    durable=self.queue_durable, exclusive=self.queue_exclusive)

    def on_queue_declareok(self, method_frame):
        """Invoked by pika when the Queue.Declare RPC call made in
        setup_queue has completed.

        In this method we will bind the queue and exchange together with the
        routing key by issuing the Queue.Bind RPC command. When this command
        is complete, the on_bindok method will be invoked by pika.

        :param pika.frame.Method method_frame: The Queue.DeclareOk frame

        """

        if self.queue == '':
            self._LOGGER.info('Binding %s to server defined queue with %s',
                              self.exchange, ','.join(self.binding_keys))
        else:
            self._LOGGER.info('Binding %s to %s with %s',
                              self.exchange, self.queue, ','.join(self.binding_keys))
        self.keys_bound_to_queue = 0
        for binding_key in self.binding_keys:
            self._channel.queue_bind(self.on_bindok, self.queue,
                                     self.exchange, binding_key)

    def on_bindok(self, unused_frame):
        """Invoked by pika when the Queue.Bind method has completed.

        At this point we will start consuming messages by calling start_consuming
        which will invoke the needed RPC commands to start the process.

        :param pika.frame.Method unused_frame: The Queue.BindOk response frame

        """
        self.keys_bound_to_queue += 1
        if self.keys_bound_to_queue == len(self.binding_keys):
            self._LOGGER.info('Queue bound')
            self.start_consuming()

    def start_consuming(self):
        """Set up the consumer.

        Calls add_on_cancel_callback so that the object is notified if RabbitMQ
        cancels the consumer. It then issues the Basic.Consume RPC command
        which returns the consumer tag that is used to uniquely identify the
        consumer with RabbitMQ. We keep the value to use it when we want to
        cancel consuming. The on_message method is passed in as a callback pika
        will invoke when a message is fully received.

        """
        self._LOGGER.info('Issuing consumer related RPC commands')
        self.add_on_cancel_callback()
        self._consumer_tag = self._channel.basic_consume(self.on_message,
                                                         self.queue)

    def add_on_cancel_callback(self):
        """Add a callback that will be invoked if RabbitMQ cancels the consumer
        for some reason. If RabbitMQ does cancel the consumer,
        on_consumer_cancelled will be invoked by pika.

        """
        self._LOGGER.info('Adding consumer cancellation callback')
        self._channel.add_on_cancel_callback(self.on_consumer_cancelled)

    def on_consumer_cancelled(self, method_frame):
        """Invoked by pika when RabbitMQ sends a Basic.Cancel for a consumer
        receiving messages.

        :param pika.frame.Method method_frame: The Basic.Cancel frame

        """
        self._LOGGER.info('Consumer was cancelled remotely, shutting down: %r',
                          method_frame)
        if self._channel:
            self._channel.close()

    def on_message(self, unused_channel, basic_deliver, properties, body):
        """Invoked by pika when a message is delivered from RabbitMQ. The
        channel is passed just for convenience. The basic_deliver object that
        is passed in carries the exchange, routing key, delivery tag and
        a redelivered flag for the message. The properties passed in is an
        instance of BasicProperties with the message properties and the body
        is the message that was sent.

        :param pika.channel.Channel unused_channel: The channel object
        :param pika.Spec.Basic.Deliver: basic_deliver method
        :param pika.Spec.BasicProperties: properties
        :param str|unicode body: The message body

        """
        self._LOGGER.debug('Received message # %s from %s',
                           basic_deliver.delivery_tag, properties.app_id)
        self._LOGGER.debug('Message Received: %s', body)
        self.consumer_callback(unused_channel, basic_deliver, properties, body)
        if not self.no_ack:
            self.acknowledge_message(basic_deliver.delivery_tag)

    def acknowledge_message(self, delivery_tag):
        """Acknowledge the message delivery from RabbitMQ by sending a
        Basic.Ack RPC method for the delivery tag.

        :param int delivery_tag: The delivery tag from the Basic.Deliver frame

        """
        self._LOGGER.debug('Acknowledging message %s', delivery_tag)
        self._channel.basic_ack(delivery_tag)

    def stop_consuming(self):
        """Tell RabbitMQ that we would like to stop consuming by sending the
        Basic.Cancel RPC command.

        """
        if self._channel:
            self._LOGGER.info('Sending a Basic.Cancel RPC command to RabbitMQ')
            self._channel.basic_cancel(self.on_cancelok, self._consumer_tag)

    def on_cancelok(self, unused_frame):
        """Invoked by pika when RabbitMQ acknowledges the cancellation of a consumer.

        At this point we will close the channel. This will invoke the
        on_channel_closed method once the channel has been closed, which will
        in-turn close the connection.

        :param pika.frame.Method unused_frame: The Basic.CancelOk frame

        """
        self._LOGGER.info(
            'RabbitMQ acknowledged the cancellation of the consumer')
        self.close_channel()

    def close_channel(self):
        """Close the channel with RabbitMQ cleanly by issuing the
        Channel.Close RPC command.

        """
        self._LOGGER.info('Closing the channel')
        self._channel.close()

    def run(self):
        """Run the example consumer by connecting to RabbitMQ and then
        starting the IOLoop to block and allow the SelectConnection to operate.

        """
        if self.safe_stop:
            signal.signal(signal.SIGTERM, self.signal_term_handler)
        self._connection = self.connect()
        self._connection.ioloop.start()

    def signal_term_handler(self, signal, frame):
        """Invoked when the signal mentioned in signal variable is 
        raised. It stops the channel and connecection etc. when called on a signal.

        :param signal signal: The signal number
        :param Frame frame: The Frame object

        """
        try:
            self.stop()
        except Exception as e:
            LOGGER.error(
                "Could not gracefully stop connection on raised signal: " + str(e))
        sys.exit(0)

    def stop(self):
        """Cleanly shutdown the connection to RabbitMQ by stopping the consumer
        with RabbitMQ.

        When RabbitMQ confirms the cancellation, on_cancelok
        will be invoked by pika, which will then close the channel and
        connection. If any exception occurs IOLoop stops but IOLoop needs to 
        be running for pika to communicate with RabbitMQ. So the IOLoop is 
        started again. All of the commands issued prior to starting
        the IOLoop will be buffered but not processed.

        """
        self._LOGGER.info('Stopping')
        self._closing = True
        self.stop_consuming()
        self._connection.ioloop.start()
        self._LOGGER.info('Stopped')

    def close_connection(self):
        """Close the connection to RabbitMQ."""
        self._LOGGER.info('Closing connection')
        self._connection.close()
