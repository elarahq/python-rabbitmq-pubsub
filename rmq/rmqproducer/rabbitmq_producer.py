import sys
import pika
import signal
import logging
from connection import RMQConnectionPool
from random import randint

class Publisher(object):
    """This is a safe and robust publisher that will handle unexpected interactions
    with RabbitMQ such as channel and connection closures.

    If RabbitMQ closes the connection, it will reopen it. You should
    look at the output, as there are limited reasons why the connection may
    be closed, which usually are tied to permission related issues or
    socket timeouts.

    It uses delivery confirmations and keeps track of messages that have been
    sent and if they've been confirmed by RabbitMQ.

    """


    def __init__(self, amqp_url, exchange, **kwargs):
        """Create a new instance of the Publisher class, passing in the
        parameters used to connect to RabbitMQ. It established connection and
        created corresponding channel with defined exchange.

        The optional arguments are:
        exchange_type, exchange_durable, exchange_auto_delete, exchange_internal,
        delivery_confirmation, nack_callback, safe_stop

        :param str amqp_url: The AMQP url to connect with
        :param str exchange: Name of exchange
        :param str exchange_type: The exchange type to use. It's default value
                is topic
        :param bool exchange_durable: Survive a reboot of RabbitMQ. This is the
                durable flag used in exchange_declare() function of pika channel.
                It's default value is True
        :param bool exchange_auto_delete: Remove when no more queues are bound
                to it. This is the auto_delete flag used in exchange_declare()
                function of pika channel. It's default value is False
        :param bool exchange_internal: Can only be published to by other
                exchanges. This is the internal flag used in exchange_declare()
                function of pika channel. It's default value is False
        :param bool delivery_confirmation: If the confirmation of published
                message is required. It's default value is True.
        :param method nack_callback: The method to callback when publishing of
                a message fails. Signature of the method: nack_callback(failed_message)
                where failed_message is the message which failed
        :param bool safe_stop: If this option is True, system will try to
                gracefully stop the connection if the process is killed (with
                SIGTERM signal). Its default value is True
        :param reconnect_time: The number of seconds after which connection will 
                automatically restart if it accidently stops. Its default value 
                is 5 seconds.

        """
        self._connection = None
        self._channel = None
        self._messages = {}
        self._message_number = 0
        self._channel_closing = False
        self._connection_closing = False
        self._LOGGER = logging.getLogger(__name__)
        self._url = amqp_url
        self.exchange = exchange
        self.parse_input_args(kwargs)
        self.connect()
        self.run()

    def parse_input_args(self, kwargs):
        """Parse and set connection parameters from a dictionary.

        Assigns defaults for missing parameters.
        """
        self.exchange_type = kwargs.get('exchange_type', 'topic')
        self.exchange_durable = kwargs.get('exchange_durable', True)
        self.exchange_auto_delete = kwargs.get('exchange_auto_delete', False)
        self.exchange_internal = kwargs.get('exchange_internal', False)
        self.delivery_confirmation = kwargs.get('delivery_confirmation', True)
        self.nack_callback = kwargs.get('nack_callback')
        self.safe_stop = kwargs.get('safe_stop', True)
        self.reconnect_time = kwargs.get('reconnect_time', 5)

    def connect(self):
        """This method connects to RabbitMQ, returning the connection handle.
        When the connection is established, the on_connection_open method
        will be invoked by pika.

        Since we want the reconnection to work, we have set stop_ioloop_on_close
        to False, which is not the default behavior of this adapter. This method 
        first searches the connection in the connection pool and creates a new 
        one if not found.

        :rtype: pika.SelectConnection

        """
        self._connection_closing = False
        self._LOGGER.info('Connecting to %s', self._url)
        connection = RMQConnectionPool.get_connection(self._url)
        if connection is None:
            connection = pika.SelectConnection(pika.URLParameters(self._url),
                                               self.on_connection_open,
                                               self.on_connection_error,
                                               stop_ioloop_on_close=False)
            self._connection = connection
        else:
            self._LOGGER.info('Connection received from connection pool')
            self._connection = connection
            # Not sure about this statement but works fine if not removed!!
            self.add_on_connection_close_callback()
            self.open_channel()

    def on_connection_open(self, unused_connection):
        """This method is called by pika once the connection to RabbitMQ has
        been established.

        It passes the handle to the connection object in case we need it, but
        in this case, we'll just mark it unused.

        :type unused_connection: pika.SelectConnection

        """
        self._LOGGER.info('Connection opened')
        self.add_on_connection_close_callback()
        self.open_channel()
    
    
    def on_connection_error(self, connection, error):
        self._LOGGER.warning("Publisher: Connection lost retrying in {time}".format(time=5))
        connection.add_timeout(5, self.reconnect)


    def add_on_connection_close_callback(self):
        """This method adds an on close callback that will be invoked by pika
        when RabbitMQ closes the connection to the publisher unexpectedly.

        """
        self._LOGGER.info('Adding connection close callback')
        self._connection.add_on_close_callback(self.on_connection_closed)

    def on_connection_closed(self, connection, reply_code, reply_text):
        """This method is invoked by pika when the connection to RabbitMQ is
        closed unexpectedly. Since it is unexpected, we will reconnect to
        RabbitMQ if it disconnects.

        :param pika.connection.Connection connection: The closed connection obj
        :param int reply_code: The server provided reply_code if given
        :param str reply_text: The server provided reply_text if given

        """
        self._channel = None
        if self._connection_closing:
            self._LOGGER.info('Connection was closed: (%s) %s',
                              reply_code, reply_text)
            self._connection.ioloop.stop()
        else:
            self._LOGGER.warning('Connection closed, reopening in %d seconds: (%s) %s',
                                 self.reconnect_time, reply_code, reply_text)
            self._connection.add_timeout(5, self.reconnect)

    def reconnect(self):
        """Will be invoked by the IOLoop timer if the connection is
        closed. See the on_connection_closed method.

        """
        unpublished_messages = self._messages
        self.reset_messages()

        # This is the old connection IOLoop instance, stop its ioloop
        self._connection.ioloop.stop()

        # Create a new connection
        self.connect()

        # There is now a new connection
        self.run()

        # Publishing if messages were unpublished before closing the connection
        if unpublished_messages:
            self._LOGGER.info("Publishing Messages left on reconnection")
            for message in unpublished_messages.values():
                self.publish_message(
                    message['message'], message['routing_key'])

    def reset_messages(self):
        """This method resets message dictionary and message counter. Since 
        message counter restarts from server side each time channel or 
        connection is restarted, we need to restart counter from client side 
        as well.

        """
        self._messages = {}
        self._message_number = 0

    def open_channel(self):
        """This method will open a new channel with RabbitMQ by issuing the
        Channel.Open RPC command. When RabbitMQ confirms the channel is open
        by sending the Channel.OpenOK RPC reply, the on_channel_open method
        will be invoked.

        """
        self._LOGGER.info('Creating a new channel')
        self._channel_closing = False
        self._connection.channel(on_open_callback=self.on_channel_open)

    def on_channel_open(self, channel):
        """This method is invoked by pika when the channel has been opened.
        The channel object is passed in so we can make use of it.

        Since the channel is now open, we'll declare the exchange to use.

        :param pika.channel.Channel channel: The channel object

        """
        self._LOGGER.info('Channel opened')
        self._channel = channel
        self.add_on_channel_close_callback()
        self.setup_exchange(self.exchange)

    def add_on_channel_close_callback(self):
        """This method tells pika to call the on_channel_closed method if
        RabbitMQ unexpectedly closes the channel.

        """
        self._LOGGER.info('Adding channel close callback')
        self._channel.add_on_close_callback(self.on_channel_closed)

    def on_channel_closed(self, channel, reply_code, reply_text):
        """Invoked by pika when RabbitMQ unexpectedly closes the channel.

        Channels are usually closed if you attempt to do something that
        violates the protocol, such as re-declare an exchange or queue with
        different parameters. Channel is restarted again if closed accidently.

        :param pika.channel.Channel: The closed channel
        :param int reply_code: The numeric reason the channel was closed
        :param str reply_text: The text reason the channel was closed

        """
        self._LOGGER.info('Channel was closed: (%s) %s',
                          reply_code, reply_text)
        self._connection.ioloop.stop()

    def reopen_channel(self):
        """This method opens the channel again and publishes the messages which 
        were left unpublished

        """
        unpublished_messages = self._messages
        self.reset_messages()
        # This is the old connection IOLoop instance, stop its ioloop
        self._connection.ioloop.stop()
        self.open_channel()
        self._connection.ioloop.start()
        if unpublished_messages:
            self._LOGGER.info(
                "Publishing Messages left on channel reopening")
            for message in unpublished_messages.values():
                self.publish_message(
                    message['message'], message['routing_key'])

    def setup_exchange(self, exchange_name):
        """Setup the exchange on RabbitMQ by invoking the Exchange.Declare RPC
        command. When it is complete, the on_exchange_declareok method will
        be invoked by pika.

        :param str|unicode exchange_name: The name of the exchange to declare

        """
        self._LOGGER.info('Declaring exchange %s', exchange_name)
        self._channel.exchange_declare(self.on_exchange_declareok, exchange_name,
                                       self.exchange_type, durable=self.exchange_durable,
                                       auto_delete=self.exchange_auto_delete,
                                       internal=self.exchange_internal)

    def on_exchange_declareok(self, unused_frame):
        """Invoked by pika when RabbitMQ has finished the Exchange.Declare RPC
        command.

        :param pika.Frame.Method unused_frame: Exchange.DeclareOk response frame

        """
        self._LOGGER.info('Exchange declared')
        self.start_publishing()

    def start_publishing(self):
        """This method will enable delivery confirmations

        """
        self._LOGGER.info('Issuing consumer related RPC commands')
        if self.delivery_confirmation:
            self.enable_delivery_confirmations()
        else:
            self._connection.ioloop.stop()

    def enable_delivery_confirmations(self):
        """Send the Confirm.Select RPC method to RabbitMQ to enable delivery
        confirmations on the channel. The only way to turn this off is to close
        the channel and create a new one.

        When the message is confirmed from RabbitMQ, the
        on_delivery_confirmation method will be invoked passing in a Basic.Ack
        or Basic.Nack method from RabbitMQ that will indicate which messages it
        is confirming or rejecting.

        """
        self._LOGGER.info('Issuing Confirm.Select RPC command')
        self._channel.confirm_delivery(self.on_delivery_confirmation)
        self._connection.ioloop.stop()

    def on_delivery_confirmation(self, method_frame):
        """Invoked by pika when RabbitMQ responds to a Basic.Publish RPC
        command, passing in either a Basic.Ack or Basic.Nack frame with
        the delivery tag of the message that was published.

        The delivery tag is an integer counter indicating the message number
        that was sent on the channel via Basic.Publish. Here we're just doing
        house keeping to keep track of stats and remove message numbers that
        we expect a delivery confirmation of from the list used to keep track
        of messages that are pending confirmation.

        :param pika.frame.Method method_frame: Basic.Ack or Basic.Nack frame

        """
        confirmation_type = method_frame.method.NAME.split('.')[1].lower()
        message_num = method_frame.method.delivery_tag
        if confirmation_type == 'ack':
            self._LOGGER.info('Message %i published successfully',
                              message_num)
            self._LOGGER.debug('The message published: %s',
                               self._messages[message_num]['message'])
        if confirmation_type == 'nack':
            self._LOGGER.error('The message %i failed to publish: %s',
                               message_num, self._messages[message_num]['message'])
            if self.nack_callback:
                self.nack_callback(self._messages[message_num]['message'])
        del self._messages[message_num]
        self._connection.ioloop.stop()

    def publish_message(self, message, routing_key):
        """This method publish a message to RabbitMQ, appending a list of 
        deliveries with the message number that was sent. This list will be 
        used to check for delivery confirmations in the on_delivery_confirmations 
        method.

        :param str message: The message to be published
        :param str routing_key: The routing key for the message to be published

        """
        if not self._channel or not self._channel.is_open or not self._connection or not self._connection.is_open:
            self.reconnect()

        self._channel.basic_publish(self.exchange, routing_key, message, properties=pika.BasicProperties(
            delivery_mode=2,  # make message persistent
        ))

        self._message_number += 1
        self._messages[self._message_number] = {
            'message': message, 'routing_key': routing_key}
        self._LOGGER.debug('Publishing message # %i', self._message_number)

        if self.delivery_confirmation:
            self._connection.ioloop.start()

    def close_channel(self):
        """Invoke this command to close the channel with RabbitMQ by sending
        the Channel.Close RPC command.

        """
        self._LOGGER.info('Closing the channel')
        if self._channel:
            self._channel.close()

    def run(self, **kwargs):
        """Run the publisher code by starting the IOLoop.

        """
        if self.safe_stop:
            signal.signal(signal.SIGTERM, self.signal_term_handler)
        self._connection.ioloop.start()

    def signal_term_handler(self, signal, frame):
        """Invoked when the signal mentioned in signal variable is
        raised. It stops the channel and connection etc. when called on a signal.

        :param signal signal: The signal number
        :param Frame frame: The Frame object

        """
        try:
            self.stop_connection()
        except Exception as e:
            self._LOGGER.error(
                "Could not gracefully stop connection on raised signal: " + str(e))
        sys.exit(0)

    def stop(self):
        """This method stops the channel and puts the connection back into the 
        connection pool. Users are strongly recommended to use this method after 
        they are done with the publishing of messages so that connection can 
        be sent back to the pool and reused by some other user saving the cost 
        of creating a new connection

        """
        self._channel_closing = True
        self.close_channel()
        if not self._connection_closing:
            RMQConnectionPool.put_connection(self._url, self._connection)
        self._connection.ioloop.start()

    def stop_connection(self):
        """This method closes the connection to RabbitMQ."""
        self._connection_closing = True
        self._LOGGER.info('Closing connection')
        self.stop()
        self._connection.close()
        self._connection.ioloop.start()
