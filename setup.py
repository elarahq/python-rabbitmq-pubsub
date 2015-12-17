from setuptools import setup


def readme():
    with open('README.rst') as f:
        return f.read()

setup(name='rmqutils',
      version='2.0.0',
      description='Rabbitmq Receiver',
      url='https://github.com/loconsolutions/python.rabbitmq.publisher_receiver',
      author='Rahul Kumar and Bipul Karnani',
      author_email='rahul.kumar@housing.com',
      license='MIT',
      packages=['rmqreceiver', 'rmqproducer'],
      install_requires=[
          'pika',
      ],
      zip_safe=False)
