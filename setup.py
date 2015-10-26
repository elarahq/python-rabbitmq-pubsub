from setuptools import setup


def readme():
    with open('README.rst') as f:
        return f.read()

setup(name='rmqreceiver',
      version='0.1',
      description='Rabbitmq Receiver',
      url='http://10.1.6.107:8034/docs/_build/html/common.html#module-common.rabbitmq_receiver',
      author='Rahul Kumar',
      author_email='rahul.kumar@housing.com',
      license='MIT',
      packages=['rmqreceiver'],
      install_requires=[
          'pika',
      ],
      zip_safe=False)
