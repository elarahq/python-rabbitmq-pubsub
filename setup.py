from setuptools import setup


def readme():
    with open('README.rst') as f:
        return f.read()

setup(name='rmq-pub-sub',
      version='2.0',
      description='Rabbitmq Receiver and Publisher',
      url='https://github.com/loconsolutions/python-rabbitmq-pubsub',
      author='Rahul Kumar and Bipul Karnani',
      author_email='rahul.kumar@housing.com',
      license='MIT',
      packages=['rmq'],
      install_requires=[
          'pika',
      ],
      zip_safe=False)
