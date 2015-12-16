from setuptools import setup


def readme():
    with open('README.rst') as f:
        return f.read()

setup(name='rmqreceiver',
      version='0.1.3',
      description='Rabbitmq Receiver',
      url='https://github.com/loconsolutions/python.rabbitmq.publisher_receiver',
      author='Rahul Kumar',
      author_email='rahul.kumar@housing.com',
      license='MIT',
      packages=['rmqreceiver', 'rmqproducer'],
      install_requires=[
          'pika',
      ],
      zip_safe=False)
