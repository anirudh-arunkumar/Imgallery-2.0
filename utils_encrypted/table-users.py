import sys, os
from env import RDS_DB_HOSTNAME, RDS_DB_USERNAME, RDS_DB_PASSWORD, RDS_DB_NAME
import pymysql.cursors
print("Connecting to RDS instance")
conn = pymysql.connect(host=RDS_DB_HOSTNAME,
             user=RDS_DB_USERNAME,
             password=RDS_DB_PASSWORD,
             db=RDS_DB_NAME,
             charset='utf8mb4',
             cursorclass=pymysql.cursors.DictCursor)

print("Connected to RDS instance")
cursor = conn.cursor ()
cursor.execute ("SELECT VERSION()")
row = cursor.fetchone ()
print("\nServer version:", row['VERSION()'])
print("\nCreating table for users.")
cursor.execute ("CREATE TABLE `User` (`userID` varchar(100) NOT NULL, `email` TEXT NOT NULL, `firstName` TEXT NOT NULL, `lastName` TEXT NOT NULL, `password` TEXT NOT NULL, `createdAt` TIMESTAMP DEFAULT CURRENT_TIMESTAMP, `updatedAt` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP, PRIMARY KEY (`userID`));")
print("\nTable for users created.")
cursor.close()
conn.close()