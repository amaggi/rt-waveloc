#!/usr/bin/env python
# -*- coding: utf-8 -*-
import pika

stations=["STA1","STA2","STA3","STA4"]

connection = pika.BlockingConnection(pika.ConnectionParameters(
        host='localhost'))
channel = connection.channel()

channel.exchange_declare(exchange='sta_data',
                         type='direct')
                         
                        
for sta in stations :
    message=" New data for "+sta
    channel.basic_publish(exchange='sta_data',
                      routing_key=sta,
                      body=message)
    print " [x] Sent %r:%r" % (sta, message)
    
connection.close()