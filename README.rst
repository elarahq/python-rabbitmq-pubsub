==========================
Python RabbitMQ Publisher and Receiver
==========================

A rabbitmq publisher and  receiver that implements a safe and reliable rabbitmq publisher and listener.

Changelog
=========

2.0
---

* Adding extra module for RabbitMQ Publisher.
**This update has backward incompatibility for Receiver class**

0.1.2
-----

* Reconnecting bug fix. Applies to all the branch.

0.1.1
-----

* Logging of message body changed to DEBUG mode instead of INFO

0.1
---

* Wrote a basic RabbitMQ Receiver

Description
===========

This package rmq-pub-sub contains two modules - rmqproducer and rmqreceiver. The module rmqreceiver has a Receiver class which can be imported to implement a rabbitmq consumer. This class contains a lot of functions for tasks like: to make connection to rabbitmq server, to change configuration of exchange and queue binding, to start listing the messages, to safely stop the connection. SelectConnection is being used by Receiver class for its asynchronous design. Similarly the module rmqproducer has a Publisher class which can be imported to implement a rabbitmq publisher.

Installation
============
To install the latest version of the package, user can use the command:
    pip install git+https://github.com/loconsolutions/python-rabbitmq-pubsub.git

To install a specific version x.x use the following command:
    pip install git+https://github.com/loconsolutions/python-rabbitmq-pubsub.git@version_x.x

for example to install version 0.1 command to be used will be:
    pip install git+https://github.com/loconsolutions/python-rabbitmq-pubsub.git@version_0.1

To uninstall the package use the command:
    pip uninstall rmq-pub-sub


Usage
=====

For documentation one can refer to the code in file rmqreceiver/rabbitmq_receiver.py and rmqproducer/rabbitmq_producer.py

To use RabbitMQ listener import the Receiver class and based on what behaviour you want from the RabbitMQ listner, pass the parameter values during initalizing the class. Here is the list of parameters (including optional params) to be passed on initializing Receiver class:

    :param method consumer_callback: The method to callback when consuming (messages)
            with the signature consumer_callback(channel, method, properties, body), where
            
                                    channel: pika.Channel,
                                    method: pika.spec.Basic.Deliver,
                                    properties: pika.spec.BasicProperties,
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

Use run() function to start the RabbitMQ listener. It will then keep on consuming the messages. Use stop() function to stop the listner whenever you want. Logging of all the events is already added in the class.


Similarly to use RabbitMQ publisher import the Publisher class and based on what behaviour you want from the RabbitMQ publisher, pass the parameter values during initalizing the class. Here is the list of parameters (including optional params) to be passed on initializing Producer class:

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

Simply initialize the class, start publishing the message using publish_message() method and stop() when done publishing. Inside the code we are maintaining a connection pool. Users are strongly recommended to use stop() method after they are done with the publishing of messages so that connection can be sent back to the pool and reused by some other user saving the cost of creating a new connection



Example
=======

Here is the sample code to use the rabbitmq receiver.

.. code:: python

    from rmq import Receiver
    def consumer_callback(unused_channel, basic_deliver, properties, body):
        #do something.
        print "The message received is: %s" % body

    def main():
        try:
            url = 'amqp://guest:guest@127.0.0.1:5672/%2F'
            exchange = 'something.something'
            exchange_type = 'topic'
            binding_key = 'something.something.*'
            queue_name='my_queue'
            my_receiver = Receiver(consumer_callback, url, exchange, 
                            binding_keys=[binding_key], queue=queue_name, 
                            queue_durable=True, queue_exclusive=False)
            # Since we haven't passed the exchange_type, it will connect to
            # existing exchange instead of initializing a new one on its own
            my_receiver.run()
            # Since safe_stop option is True (by default), when a kill 
            # process signal is raised my_receiver.stop() function will be 
            # automatically called before the process ends
        except KeyboardInterrupt:
            my_receiver.stop()

    if __name__ == '__main__':
        main()

A sample code to use the rabbitmq publisher

.. code:: python

    import time
    import logging
    from rmq import Publisher

    logging.basicConfig(level=logging.INFO)

    my_publisher = Publisher(
        'amqp://guest:guest@localhost:5672/%2F?connection_attempts=3&heartbeat_interval=3600', 'my.exchange.name')
    # Make sure exchange doesn't already exist with different properties

    for count in range(1, 6):
        my_publisher.publish_message(
            "message number {num}".format(num=count), 'my.routing.key')
        time.sleep(1)
    my_publisher.stop()
    # Users are strongly recommended to use stop() method after they are done
    # with the publishing of messages so that connection can be sent back to
    # the connection pool and reused by some other user saving the cost of
    # creating a new connection
