from rmq import Receiver, Publisher


def callback(self, ch, method,properties, body):
    print("message received")


publisher = Publisher('amqp://guest:guest@10.1.6.46:5672/%2F/?socket_timeout=10', 'analytics_new')
receiver = Receiver(callback, 'amqp://guest:guest@10.1.6.46:5672/%2F/?socket_timeout=10', 'analytics_new', binding_keys=["#"], queue='dsl_profiling_service')
receiver.run()
