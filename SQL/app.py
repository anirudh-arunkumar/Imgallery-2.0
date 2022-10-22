#!flask/bin/python
import sys, os
sys.path.append(os.path.abspath(os.path.join('..', 'utils')))
from env import AWS_ACCESS_KEY, AWS_SECRET_ACCESS_KEY, AWS_REGION, PHOTOGALLERY_S3_BUCKET_NAME, RDS_DB_HOSTNAME, RDS_DB_USERNAME, RDS_DB_PASSWORD, RDS_DB_NAME, URL_SOURCE, EMAIL_S, SERIALIZER_HASH
from flask import Flask, jsonify, abort, request, make_response, url_for, session
from flask import render_template, redirect
import time
import boto3
import bcrypt
import uuid
from datetime import datetime
from pytz import timezone
from itsdangerous import URLSafeTimedSerializer
from datetime import timedelta
import exifread
import json
import pymysql.cursors


app = Flask(__name__, static_url_path="")
app.secret_key = "abc"
UPLOAD_FOLDER = os.path.join(app.root_path,'static','media')
ALLOWED_EXTENSIONS = set(['png', 'jpg', 'jpeg'])

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def getExifData(path_name):
    f = open(path_name, 'rb')
    tags = exifread.process_file(f)
    ExifData={}
    for tag in tags.keys():
        if tag not in ('JPEGThumbnail', 'TIFFThumbnail', 'Filename', 'EXIF MakerNote'):
            key="%s"%(tag)
            val="%s"%(tags[tag])
            ExifData[key]=val
    return ExifData

def s3uploading(filename, filenameWithPath, uploadType="photos"):
    s3 = boto3.client('s3', aws_access_key_id=AWS_ACCESS_KEY,
                            aws_secret_access_key=AWS_SECRET_ACCESS_KEY)             
    bucket = PHOTOGALLERY_S3_BUCKET_NAME
    path_filename = uploadType + "/" + filename
    s3.upload_file(filenameWithPath, bucket, path_filename)  
    s3.put_object_acl(ACL='public-read', Bucket=bucket, Key=path_filename)
    return f'''http://{PHOTOGALLERY_S3_BUCKET_NAME}.s3.amazonaws.com/{path_filename}'''

def get_database_connection():
    conn = pymysql.connect(host=RDS_DB_HOSTNAME,
                             user=RDS_DB_USERNAME,
                             password=RDS_DB_PASSWORD,
                             db=RDS_DB_NAME,
                             charset='utf8mb4',
                             cursorclass=pymysql.cursors.DictCursor)
    return conn

def send_email(email, body):
    try:
        ses = boto3.client('ses', aws_access_key_id=AWS_ACCESS_KEY,
                                aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
                                region_name=AWS_REGION)
        ses.send_email(
            Source=EMAIL_S,
            Destination={'ToAddresses': [email]},
            Message={
                'Subject': {'Data': 'Photo Gallery: Confirm Your Account'},
                'Body': {'Text': {'Data': body}}
            }
        )
    except Exception as exception:
        return False
    else:
        return True


@app.errorhandler(400)
def bad_request(error):
    """ 400 page route.

    get:
        description: Endpoint to return a bad request 400 page.
        responses: Returns 400 object.
    """
    return make_response(jsonify({'error': 'Bad request'}), 400)

@app.errorhandler(404)
def not_found(error):
    """ 404 page route.

    get:
        description: Endpoint to return a not found 404 page.
        responses: Returns 404 object.
    """
    return make_response(jsonify({'error': 'Not found'}), 404)



@app.route('/', methods=['GET'])
def home_page():
    """ Home page route.

    get:
        description: Endpoint to return home page.
        responses: Returns all the albums.
    """
    if 'user' in session:
        conn=get_database_connection()
        cursor = conn.cursor ()
        cursor.execute("SELECT * FROM photogallerydb.Album;")
        results = cursor.fetchall()
        conn.close()
        items=[]
        for item in results:
            album={}
            album['albumID'] = item['albumID']
            album['name'] = item['name']
            album['description'] = item['description']
            album['thumbnailURL'] = item['thumbnailURL']

            createdAt = datetime.strptime(str(item['createdAt']), "%Y-%m-%d %H:%M:%S")
            createdAt_UTC = timezone("UTC").localize(createdAt)
            album['createdAt']=createdAt_UTC.astimezone(timezone("US/Eastern")).strftime("%B %d, %Y")

            items.append(album)

        return render_template('index.html', albums=items)
    else:
        return redirect('/login')


@app.route('/login', methods=['GET', 'POST'])
def login_page():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        password = password.encode('utf-8')
        conn=get_database_connection()
        cursor = conn.cursor ()
        statement1 = f'''SELECT userID, password, email, validated FROM photogallerydb.User WHERE email="{email}";'''
        cursor.execute(statement1)
        results = cursor.fetchall()
        conn.commit()
        conn.close()
        if len(results) != 0:
            for item in results:
                if item['validated'] == 1 and bcrypt.checkpw(password, item['password'].encode('utf-8')):
                    session['user'] = item['userID']
                    session.permanent = True
                    app.permanent_session_lifetime = timedelta(minutes=5)
                    return redirect('/')
                else:
                    return render_template('login.html')
        else:
            return redirect('/login')
    else:
        return render_template('login.html')


@app.route('/signup', methods=['POST', 'GET'])
def signup_page():
    if request.method == 'POST':
        userID = uuid.uuid4()
        email = request.form['email']
        firstName = request.form['firstName']
        lastName = request.form['lastName']
        password = request.form['password']
        password = password.encode('utf-8') 
        hashedPass = bcrypt.hashpw(password, bcrypt.gensalt())
        conn=get_database_connection()
        cursor = conn.cursor ()
        statement1 = f'''SELECT userID, email FROM photogallerydb.User WHERE userID="{userID}" or email="{email}";'''
        cursor.execute(statement1)
        results = cursor.fetchall()
        if len(results) != 0:
            return render_template('signup.html')
        else:
            serializer = URLSafeTimedSerializer(SERIALIZER_HASH)
            token = serializer.dumps(email, salt='activation')
            contentofEmail = "Please Click the Link to Authenticate your Account \n" + URL_SOURCE + ":5000" + "/confirm/" + token
            send_email(email, contentofEmail)
            statement2 = f'''INSERT INTO photogallerydb.User (userId, email, firstName, lastName, password, validated) VALUES ("{userID}", "{email}", "{firstName}", "{lastName}", "{hashedPass.decode('utf-8')}", "FALSE");'''    
            result2 = cursor.execute(statement2)
            conn.commit()
            conn.close()
            return redirect('/')
    else:
        return render_template('signup.html')

@app.route('/confirm/<string:ID>', methods=['GET'])
def confirm_user(ID):
    try:
        serializer = URLSafeTimedSerializer(SERIALIZER_HASH)
        email = serializer.loads(
            ID,
            salt='activation',
            max_age=600)
        conn=get_database_connection()
        cursor = conn.cursor ()
        statement1 = f'''UPDATE photogallerydb.User SET validated="1" WHERE email="{email}";'''
        result1 = cursor.execute(statement1)
        conn.commit()
        conn.close()
        return redirect('/')
    except Exception as e:
        return render_template('login.html')

@app.route('/createAlbum', methods=['GET', 'POST'])
def add_album():
    if request.method == 'POST':
        uploadedFileURL=''
        file = request.files['imagefile']
        name = request.form['name']
        description = request.form['description']
        userID = session['user']

        if file and allowed_file(file.filename):
            albumID = uuid.uuid4()
            
            filename = file.filename
            filenameWithPath = os.path.join(UPLOAD_FOLDER, filename)
            file.save(filenameWithPath)
            
            uploadedFileURL = s3uploading(str(albumID), filenameWithPath, "thumbnails");

            conn=get_database_connection()
            cursor = conn.cursor ()
            statement = f'''INSERT INTO photogallerydb.Album (albumID, name, description, thumbnailURL, userID) VALUES ("{albumID}", "{name}", "{description}", "{uploadedFileURL}","{userID}");'''
            
            result = cursor.execute(statement)
            conn.commit()
            conn.close()

        return redirect('/')
    else:
        return render_template('albumForm.html')



@app.route('/album/<string:albumID>', methods=['GET'])
def view_photos(albumID):
    """ Album page route.

    get:
        description: Endpoint to return an album.
        responses: Returns all the photos of a particular album.
    """
    conn=get_database_connection()
    cursor = conn.cursor ()
    # Get title
    statement = f'''SELECT * FROM photogallerydb.Album WHERE albumID="{albumID}";'''
    cursor.execute(statement)
    albumMeta = cursor.fetchall()
    
    # Photos
    statement = f'''SELECT photoID, albumID, title, description, photoURL FROM photogallerydb.Photo WHERE albumID="{albumID}";'''
    cursor.execute(statement)
    results = cursor.fetchall()
    conn.close() 
    
    items=[]
    for item in results:
        photos={}
        photos['photoID'] = item['photoID']
        photos['albumID'] = item['albumID']
        photos['title'] = item['title']
        photos['description'] = item['description']
        photos['photoURL'] = item['photoURL']
        items.append(photos)

    return render_template('viewphotos.html', photos=items, albumID=albumID, albumName=albumMeta[0]['name'])

@app.route('/album/<string:albumID>/delete', methods=['GET'])
def delete_photos(albumID):
    conn=get_database_connection()
    cursor = conn.cursor ()
    # Photos
    statement = f'''DELETE FROM photogallerydb.Photo WHERE albumID="{albumID}";'''
    cursor.execute(statement)
    conn.commit()
    conn.close() 
    return redirect('/album/'+albumID)

@app.route('/cancelUser', methods=['GET'])
def cancel_user():
    userID = session['user']
    conn=get_database_connection()
    cursor = conn.cursor ()
    #ALBUMS
    statement = f'''SELECT albumID FROM photogallerydb.Album WHERE userID="{userID}";'''
    cursor.execute(statement)
    results = cursor.fetchall()
    for item in results:
        delete_photos(item["albumID"])
    statement = f'''DELETE FROM photogallerydb.Album WHERE userID="{userID}";'''
    cursor.execute(statement)
    conn.commit()
    conn.close() 
    return redirect('/')

@app.route('/album/<string:albumID>/<string:photoID>/update', methods=['GET', 'POST'])
def update_photo(albumID, photoID):
    if request.method == 'POST': 
        title = request.form['title']
        description = request.form['description']
        tags = request.form['tags']
        conn=get_database_connection()
        cursor = conn.cursor ()
        statement = f'''UPDATE photogallerydb.Photo SET title="{title}", description="{description}", tags="{tags}" WHERE photoID="{photoID}";'''        
        cursor.execute(statement)
        conn.commit()
        conn.close() 
        return redirect('/album/'+albumID +'/photo/'+photoID)
    else:
        return render_template('updatePhoto.html', photoID=photoID, albumID=albumID)

@app.route('/album/<string:albumID>/addPhoto', methods=['GET', 'POST'])
def add_photo(albumID):
    """ Create new photo under album route.

    get:
        description: Endpoint to return form to create a new photo.
        responses: Returns all the fields needed to store a new photo.

    post:
        description: Endpoint to send new photo.
        responses: Returns user to album page.
    """
    if request.method == 'POST':    
        uploadedFileURL=''
        file = request.files['imagefile']
        title = request.form['title']
        description = request.form['description']
        tags = request.form['tags']

        if file and allowed_file(file.filename):
            photoID = uuid.uuid4()
            filename = file.filename
            filenameWithPath = os.path.join(UPLOAD_FOLDER, filename)
            file.save(filenameWithPath)            
            
            uploadedFileURL = s3uploading(filename, filenameWithPath);
            
            ExifData=getExifData(filenameWithPath)

            conn=get_database_connection()
            cursor = conn.cursor ()
            ExifDataStr = json.dumps(ExifData)
            statement = f'''INSERT INTO photogallerydb.Photo (PhotoID, albumID, title, description, tags, photoURL, EXIF) VALUES ("{photoID}", "{albumID}", "{title}", "{description}", "{tags}", "{uploadedFileURL}", %s);'''
            
            result = cursor.execute(statement, (ExifDataStr,))
            conn.commit()
            conn.close()

        return redirect(f'''/album/{albumID}''')
    else:
        conn=get_database_connection()
        cursor = conn.cursor ()
        # Get title
        statement = f'''SELECT * FROM photogallerydb.Album WHERE albumID="{albumID}";'''
        cursor.execute(statement)
        albumMeta = cursor.fetchall()
        conn.close()

        return render_template('photoForm.html', albumID=albumID, albumName=albumMeta[0]['name'])



@app.route('/album/<string:albumID>/photo/<string:photoID>', methods=['GET'])
def view_photo(albumID, photoID):  
    conn=get_database_connection()
    cursor = conn.cursor ()

    # Get title
    statement = f'''SELECT * FROM photogallerydb.Album WHERE albumID="{albumID}";'''
    cursor.execute(statement)
    albumMeta = cursor.fetchall()

    statement = f'''SELECT * FROM photogallerydb.Photo WHERE albumID="{albumID}" and photoID="{photoID}";'''
    cursor.execute(statement)
    results = cursor.fetchall()
    conn.close()

    if len(results) > 0:
        photo={}
        photo['photoID'] = results[0]['photoID']
        photo['title'] = results[0]['title']
        photo['description'] = results[0]['description']
        photo['tags'] = results[0]['tags']
        photo['photoURL'] = results[0]['photoURL']
        photo['EXIF']=json.loads(results[0]['EXIF'])

        createdAt = datetime.strptime(str(results[0]['createdAt']), "%Y-%m-%d %H:%M:%S")
        updatedAt = datetime.strptime(str(results[0]['updatedAt']), "%Y-%m-%d %H:%M:%S")

        createdAt_UTC = timezone("UTC").localize(createdAt)
        updatedAt_UTC = timezone("UTC").localize(updatedAt)

        photo['createdAt']=createdAt_UTC.astimezone(timezone("US/Eastern")).strftime("%B %d, %Y at %-I:%M:%S %p")
        photo['updatedAt']=updatedAt_UTC.astimezone(timezone("US/Eastern")).strftime("%B %d, %Y at %-I:%M:%S %p")
        
        tags=photo['tags'].split(',')
        exifdata=photo['EXIF']
        
        return render_template('photodetail.html', photo=photo, tags=tags, exifdata=exifdata, albumID=albumID, albumName=albumMeta[0]['name'])
    else:
        return render_template('photodetail.html', photo={}, tags=[], exifdata={}, albumID=albumID, albumName="")

@app.route('/album/<string:albumID>/<string:photoID>/delete', methods=['GET'])
def delete_photo(albumID, photoID):
    conn=get_database_connection()
    cursor = conn.cursor ()
    # Delete the Photo we are looking at
    statement = f'''DELETE FROM photogallerydb.Photo WHERE photoID="{photoID}";'''
    cursor.execute(statement)
    conn.commit()
    conn.close() 
    return redirect('/album/'+albumID)

@app.route('/album/search', methods=['GET'])
def search_album_page():
    """ search album page route.

    get:
        description: Endpoint to return all the matching albums.
        responses: Returns all the albums based on a particular query.
    """ 
    query = request.args.get('query', None)

    conn=get_database_connection()
    cursor = conn.cursor ()
    statement = f'''SELECT * FROM photogallerydb.Album WHERE name LIKE '%{query}%' UNION SELECT * FROM photogallerydb.Album WHERE description LIKE '%{query}%';'''
    cursor.execute(statement)

    results = cursor.fetchall()
    conn.close()

    items=[]
    for item in results:
        album={}
        album['albumID'] = item['albumID']
        album['name'] = item['name']
        album['description'] = item['description']
        album['thumbnailURL'] = item['thumbnailURL']
        items.append(album)

    return render_template('searchAlbum.html', albums=items, searchquery=query)



@app.route('/album/<string:albumID>/search', methods=['GET'])
def search_photo_page(albumID):
    query = request.args.get('query', None)

    conn=get_database_connection()
    cursor = conn.cursor ()
    statement = f'''SELECT * FROM photogallerydb.Photo WHERE title LIKE '%{query}%' AND albumID="{albumID}" UNION SELECT * FROM photogallerydb.Photo WHERE description LIKE '%{query}%' AND albumID="{albumID}" UNION SELECT * FROM photogallerydb.Photo WHERE tags LIKE '%{query}%' AND albumID="{albumID}" UNION SELECT * FROM photogallerydb.Photo WHERE EXIF LIKE '%{query}%' AND albumID="{albumID}";'''
    cursor.execute(statement)
    results = cursor.fetchall()
    conn.close()
    items=[]
    for item in results:
        photo={}
        photo['photoID'] = item['photoID']
        photo['albumID'] = item['albumID']
        photo['title'] = item['title']
        photo['description'] = item['description']
        photo['photoURL'] = item['photoURL']
        items.append(photo)
    return render_template('searchPhoto.html', photos=items, searchquery=query, albumID=albumID)

if __name__ == '__main__':
    app.run(debug=True, host="0.0.0.0", port=5000)