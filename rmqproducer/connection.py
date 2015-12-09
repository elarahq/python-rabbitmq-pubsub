from rabbitmq_producer import Publisher

class RMQCoonectionPool(object):
    connection_pools = {}

    @classmethod
    def get_connection(cls, amqp_url):
        connection_identifier = amqp_url
        connection = cls.connection_pools.get(connection_identifier)
        if connection is None:
            publisher_object = Publisher(amqp_url)
            connection = publisher_object.connect()
            connection_pools[connection_identifier] = connection

        return connection
