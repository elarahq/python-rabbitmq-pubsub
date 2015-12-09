from rabbitmq_producer import Publisher


class RMQCoonectionPool(object):
    """This is Connection Pool from which user can take/put a conncetion

    """
    # connection_pools is a dictionary that stores Publisher objects
    connection_pools = {}

    @classmethod
    def get_connection(cls, amqp_url):
        """This method is used to get the connection from the connection pool. 
        If the connection isn't already there in the pool, it will make a new 
        connection and store it in the conncetion pool. Please note that 
        instead of storing the connection, we are storing corresponding 
        Publisher object

        """
        connection_identifier = amqp_url
        publisher_object = cls.connection_pools.get(connection_identifier)
        if publisher_object is None:
            publisher_object = Publisher(amqp_url)
            publisher_object.connect()
            cls.connection_pools[connection_identifier] = publisher_object
        return publisher_object
