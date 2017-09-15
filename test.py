from rmq import Receiver


def callback(self, ch, method,properties, body):
    print("message received")


receiver = Receiver(callback, 'amqp://guest:guest@10.1.6.46:5672/%2F/?socket_timeout=10', 'analytics_new', binding_keys=["#"], queue='dsl_profiling_service')
receiver.run()
