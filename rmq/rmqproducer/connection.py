import Queue
from collections import defaultdict


class RMQConnectionPool(object):
    """This is Connection Pool from which user can take/put a conncetion

    """
    # connection_pools is a dictionary that stores Publisher objects
    connection_pools = defaultdict(Queue.Queue)

    @classmethod
    def get_connection(cls, amqp_url):
        """This method is used to get the connection from the connection pool. 
        If the connection isn't already there in the pool, it will make a new 
        connection and store it in the conncetion pool. Please note that 
        instead of storing the connection, we are storing corresponding 
        Publisher object

        """
        connection_identifier = amqp_url
        connection_object = None
        try:
            connection_object = cls.connection_pools[connection_identifier].get_nowait()
        except Queue.Empty as e:
            pass
        return connection_object

    @classmethod
    def put_connection(cls, connection_identifier, connection_object):
        """This method is used to put the new connection in the connection pool.
        This is invoked when the connection is not available for that identifier.
        """
        cls.connection_pools[connection_identifier].put(connection_object)

    @classmethod
    def remove_connection(cls, connection_identifier):
        """This method removes the connection from the pool for the given identifier.
        """
        cls.connection_pools.pop(connection_identifier, None)