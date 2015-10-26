This is rabbitmq receiver that implements a safe and reliable rabbitmq listener. Latest version of package is 0.1

Name of the package is rmqreceiver. It has a Receiver class which can be imported to implement a rabbitmq consumer. This class provides a lot of fucntions for tasks like: to make connection to rabbitmq server, to change configuration of exchange and queue binding, to start listing the messages, to safely stop the connection.

To install the latest version of the package, user can use the command:
pip install git+https://github.com/loconsolutions/python.rabbitmq.receiver.git

To install a specific version x.x use the following command:
pip install git+https://github.com/loconsolutions/python.rabbitmq.receiver.git@version_x.x

for example to install version 0.1 command to be used will be:
pip install git+https://github.com/loconsolutions/python.rabbitmq.receiver.git@version_0.1

For documentation one can refer to the code in file rmqreceiver/rabbitmq_receiver.py

Here is the list of parameters (including optional params) to be passed on initializing Receiver class:

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



Here is the sample code to use the rabbitmq receiver::

    from rmqreceiver import Receiver
    def consumer_callback(unused_channel, basic_deliver, properties, body):
        #do something.
        pass

    def main():
        url = 'amqp://guest:guest@127.0.0.1:5672/%2F'
        exchange = 'something.something'
        exchange_type = 'topic'
        binding_key = 'something.something.*'
        queue_name='my_queue'
        my_receiver = Receiver(consumer_callback, url, exchange, binding_keys=[binding_key], queue=queue_name, queue_durable=True, queue_exclusive=False)
        my_receiver.run()

    if __name__ == '__main__':
        main()
