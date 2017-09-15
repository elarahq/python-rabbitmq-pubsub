from rmq import Publisher


def callback(self, ch, method,properties, body):
    print("message received")


receiver = Publisher('amqp://guest:guest@10.1.6.46:5672/%2F/?socket_timeout=10', 'analytics_new')
