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

print("\nCreating table for albums.")
cursor.execute ("CREATE TABLE `Album` (`albumID` varchar(100) NOT NULL, `name` TEXT NOT NULL, `description` TEXT NOT NULL, `thumbnailURL` TEXT NOT NULL, `createdAt` TIMESTAMP DEFAULT CURRENT_TIMESTAMP, PRIMARY KEY (`albumID`));")
print("\nTable for albums created.")

print("\nCreating table for photos.")
cursor.execute ("CREATE TABLE `Photo` (`photoID` varchar(100) NOT NULL, `albumID` varchar(100) NOT NULL, `title` TEXT, `description` TEXT, `tags` TEXT, `photoURL` TEXT NOT NULL, `EXIF` TEXT, `createdAt` TIMESTAMP DEFAULT CURRENT_TIMESTAMP, `updatedAt` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP, PRIMARY KEY (`photoID`), FOREIGN KEY (`albumID`) REFERENCES `Album` (`albumID`) ON DELETE CASCADE ON UPDATE CASCADE);")
print("\nTable for photos created.")

cursor.close()
conn.close()