# encoding: utf-8
from __future__ import print_function

from decimal import Decimal
from datetime import datetime, date, timedelta

import logging

import server_config

# Import smtplib for the actual sending function
import smtplib

# Here are the email package modules we'll need
from email.mime.image import MIMEImage
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

import sys

COMMASPACE = ', '

def sendEmail(recepients, subject, message):
  msg = MIMEMultipart('alternative')
  msg['Subject'] = subject
  me = 'no-reply@16colorgames.com'
  msg['From'] = me
  msg['To'] = COMMASPACE.join(recepients)
  body = MIMEText(message, 'plain', 'utf-8')
  msg.attach(body)
  
  s = smtplib.SMTP('localhost')
  s.set_debuglevel(1)
  s.ehlo()
  s.starttls()
  s.ehlo
  
  s.sendmail(me, recepients, msg.as_string())
  s.quit()

  return