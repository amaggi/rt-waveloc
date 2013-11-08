#!/usr/bin/env python
import pika, sys

stations=["STA1","STA2","STA3","STA4"]

connection = pika.BlockingConnection(pika.ConnectionParameters(
        host='localhost'))
channel = connection.channel()

channel.exchange_declare(exchange='sta_data',
                         type='direct')

result = channel.queue_declare(exclusive=True)
queue_name = result.method.queue



for sta in stations :
    channel.queue_bind(exchange='sta_data',
                   queue=queue_name,
                   routing_key=sta)

print ' [*] Waiting for data. To exit press CTRL+C'

def callback(ch, method, properties, body):
    print " [x] %r:%r" % (method.routing_key, body,)

channel.basic_consume(callback,
                      queue=queue_name,
                      no_ack=True)

channel.start_consuming()