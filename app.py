from functools import wraps
import sys
import os
import datetime
from flask import Flask, render_template, redirect, request, url_for, session, Response, jsonify, redirect
#coming from pyrebase4
import pyrebase
from werkzeug.utils import secure_filename
import tensorflow as tf
from tensorflow import keras
import re
import base64
from tensorflow.keras.applications.resnet50 import decode_predictions, preprocess_input
from tensorflow.keras.models import load_model
from tensorflow.keras.preprocessing import image
# Some utilites
import numpy as np
from PIL import Image
from io import BytesIO
from datetime import timedelta
def base64_to_pil(img_base64):
    """
    Convert base64 image data to PIL image
    """
    image_data = re.sub(img_base64)
    pil_image = Image.open(BytesIO(image_data))
    return pil_image
def np_to_base64(img_np):
    """
    Convert numpy image (RGB) to base64 string
    """
    img = Image.fromarray(img_np.astype('uint8'), 'RGB')
    buffered = BytesIO()
    img.save(buffered, format="PNG")
    return u"data:image/png;base64," + base64.b64encode(buffered.getvalue()).decode("ascii")
# You can use pretrained model from Keras
# Check https://keras.io/applications/
from keras.applications.mobilenet_v2 import MobileNetV2
model = MobileNetV2(weights='imagenet')

print('Model loaded. Check http://127.0.0.1:5000/')

# Model saved with Keras model.save()
MODEL_PATH = 'flower_model1.h5'
# Load your own trained model
#model = load_model(MODEL_PATH)
#model._make_predict_function()          # Necessary
print('Model loaded. Start serving...')

def model_predict(img, model):
    img = img.resize((224, 224))

    # Preprocessing the image
    x = image.img_to_array(img)
    # x = np.true_divide(x, 255)
    x = np.expand_dims(x, axis=0)

    # Be careful how your trained model deals with the input
    # otherwise, it won't make correct prediction!
    x = preprocess_input(x, mode='tf')
    preds = model.predict(x)
    return preds
#firebase config
config = {

}

#init firebase
firebase = pyrebase.initialize_app(config)
#auth instance
auth = firebase.auth()
#real time database instance
db = firebase.database()

storage = firebase.storage()
#new instance of Flask
app = Flask(__name__)
#secret key for the session
app.secret_key = os.urandom(24)


#decorator to protect routes
def isAuthenticated(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        #check for the variable that pyrebase creates
        if not auth.current_user != None:
            return redirect(url_for('signup'))
        return f(*args, **kwargs)
    return decorated_function


@app.route("/")
def index():

    allposts = db.child("Posts").get()
    stats = db.child("Stats").get()
    allcommunities = db.child("Communities").get()
    allnews = db.child("News_posts").get()
    top_post = db.child("Posts").get()
    #print(allposts.val(), file=sys.stderr)
    if allposts.val() == None  :
      #print(posts, file=sys.stderr)
      return render_template("index.html")
    else:
      return render_template("index.html", posts=allposts, storage=storage, communities = allcommunities, top_post=top_post, stats=stats, news="news", images="images", news_post=allnews)

#all latest posts route
@app.route("/latest_posts", methods=["POST","GET"])
def latest_posts():
    allposts = db.child("Posts").get()
    if request.method == "POST":
        search_request = request.form["search_bar"]
        allposts = db.child("Posts").get()
        return render_template("latest_posts.html", posts=allposts, storage=storage, search_request=search_request, news="news", images="images")
    if allposts.val() == None:
      return render_template("latest_posts.html")
    else:
      return render_template("latest_posts.html", posts=allposts, storage=storage, news="news", images="images")

#signup route
@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
      #get the request form data
      username = request.form["username"]
      email = request.form["email"]
      password = request.form["password"]
      user_name = {
          "username" : username, 
          "time" : str(datetime.datetime.now()),
          "email" : email
      }
      try:
        #create the user
        auth.create_user_with_email_and_password(email, password)
        #login the user right away
        user = auth.sign_in_with_email_and_password(email, password)
        #session
        user_id = user['idToken']
        user_email = email
        session['usr'] = user_id
        session["email"] = user_email
        session.permanent = True
        db.child("Accounts").push(user_name)
        return redirect("/")
      except:
        return render_template("signup.html", message="The email is already taken, try another one, please" )
    return render_template("signup.html")
#login route
@app.route("/login", methods=["GET", "POST","FORGOT"])
def login():
    if request.method == "FORGOT":
        email1 = request.form["email1"]
        auth.send_password_reset_email(email1)
        return render_template("login.html", message="Please check your emails to reset password..." )
    if request.method == "POST":
      #get the request data
      email = request.form["email"]
      password = request.form["password"]
      try:
        session.permanent = True
        app.permanent_session_lifetime = timedelta(days=1)
        #login the user
        user = auth.sign_in_with_email_and_password(email, password)
        #set the session
        user_id = user['idToken']
        user_email = email
        session["usr"] = user_id
        session["email"] = user_email
        return redirect("/")
      except:
        return render_template("login.html", message="Wrong Credentials" )
    return render_template("login.html")

@app.route("/map")
def map():
    allposts = db.child("Posts").get()
    return render_template("map.html", posts=allposts)
@app.route("/sitemap")
def sitemap():
    return render_template("sitemap.xml")


@app.route("/plane_classifier", methods=["GET", "POST"])
def plane_classifier():
    if request.method == "POST":
        upload = request.files['upload']
        preds = model_predict(Image.open(upload), model)
        pred_proba = "{:.3f}".format(np.amax(preds))    # Max probability
        pred_class = decode_predictions(preds, top=1)   # ImageNet Decode
        result = str(pred_class[0][0][1])               # Convert to string
        result = result.replace('_', ' ').capitalize()
        return render_template("plane_classifier.html", message = result)

    return render_template("plane_classifier.html")
#logout route
@app.route("/logout")
def logout():
    #remove the token setting the user to None
    auth.current_user = None
    #also remove the session
    session['usr'] = ""
    session["email"] = ""
    session.clear()
    return redirect("/")

#create form

@app.route("/create_news_post", methods=["GET", "POST"])
def create_news_post():
    if request.method == "POST":
        title = request.form["title"]
        content = request.form["content"]
        content = content.split("\n") 
        upload = request.files['upload']
        community = request.form["community"]
        image_address = (str(datetime.datetime.now()) + "_" + title)
        storage.child("images/" + image_address).put(upload)
        post = {
            "title": title,
            "type_of_post:" : "news",
            "image_address": image_address,
            "content": content,
            "author": session["email"],
            "time" : str(datetime.datetime.now()),
            "community" : community
            }
        try:
      #print(title, content, file=sys.stderr)
      #push the post object to the database
            db.child("News_posts").push(post)
            return redirect("/")
        except:
            return render_template("create_news_post.html", message= "Something wrong happened")
    return render_template("create_news_post.html", news=news)
@app.route("/create", methods=["GET", "POST","post_image","NEWS", "POST_image","POST_news"])
def create():
    location = ""
    communities = db.child("Communities").get()
    if request.method == "POST":
    #get the request data
        title = request.form["title"]
        content = request.form["content"]
        content = content.split("\n") 
        upload = request.files['upload']
        latitude = request.form["latitude"]
        longitude = request.form["longitude"]
        community = request.form["community"]
        image_address = (str(datetime.datetime.now()) + "_" + session['usr'] + title)
        storage.child("images/" + image_address).put(upload)
        #img = base64_to_pil(upload)
        #preds = model_predict(Image.open(upload), model)
        #pred_proba = "{:.3f}".format(np.amax(preds))    # Max probability
        #pred_class = decode_predictions(preds, top=1)   # ImageNet Decode
        #result = str(pred_class[0][0][1])               # Convert to string
        #result = result.replace('_', ' ').capitalize()
        post = {
            "title": title,
            "type_of_post:" : "images",
            "content": content,
            "type" : "unknown",
            "likes" : 0,
            "image_address": image_address,
            "author": session["email"],
            "time" : str(datetime.datetime.now()),
            "latitude" : latitude,
            "longitude" : longitude,
            "community" : community
            }

        web_stats = {
            "latest_post" : image_address
        }
        try:
      #print(title, content, file=sys.stderr)
      #push the post object to the database
            db.child("Posts").push(post)
            db.child("Stats").update(web_stats)
            return redirect("/")
        except:
            return render_template("create.html", message= "Something wrong happened", communities=communities)
    return render_template("create.html", news=news, communities=communities)

@app.route("/my_account", methods=["GET","POST"])
def my_account():
    user_account = db.child("Accounts").get()
    user_n = session["email"]
    my_posts = db.child("Posts").get()
    my_news_posts = db.child("News_posts").get()
    if my_posts.val() == None or my_news_posts.val() == None:
      #print(posts, file=sys.stderr)
      return render_template("my_account.html", user_account=user_account, user_n = user_n)
    else:
        return render_template("my_account.html", my_news_posts=my_news_posts,user_account=user_account, user_n = user_n, my_posts=my_posts, storage=storage)
@app.route("/news", methods=["GET","POST"])
def news():
    allposts_news = db.child("News_posts").get()
    if request.method == "POST":
        search_request = request.form["search_bar"]
        allposts = db.child("News_posts").get()
        return render_template("news.html", posts=allposts, search_request=search_request)
    if allposts_news.val() == None:
      return render_template("news.html")
    else:
      return render_template("news.html", posts=allposts_news, news="news", storage=storage)

@app.route("/news_post/<id>", methods=["GET","POST"])
def news_post(id):
    allcomments = db.child("News_posts/"+id+"/Comments").get()
    orderedDict =  db.child("News_posts").order_by_key().equal_to(id).limit_to_first(1).get()
    if request.method == "POST":
        comment1 = request.form["comment_"]
        comments12 = {
            "comment":comment1,
            "post id" : id,
            "time" : str(datetime.datetime.now())
                }
        try:
            db.child("News_posts/"+id+"/Comments").push(comments12)
            return redirect("/news_post/" + id)
        except:
            return render_template("/news_post/" + id, message= "Something wrong happened")
    if allcomments.val() == None:
        #print(posts, file=sys.stderr)
        return render_template("news_posts.html", data=orderedDict, id=id, storage=storage)

    return render_template("news_posts.html", data=orderedDict, storage=storage, comments= allcomments)
 

@app.route("/communities", methods=["GET","POST"])
def communities():
    if request.method == "POST":
        search_request = request.form["search_bar"]
        allcommunities = db.child("Communities").get()
        return render_template("communities.html", posts=allcommunities, search_request=search_request)
    
    allcommunities = db.child("Communities").get()
    if allcommunities.val() == None:
      return render_template("communities.html")
    else:
      return render_template("communities.html", posts=allcommunities)

@app.route("/create_community", methods=["GET", "POST"])
@isAuthenticated
def create_community():

    if request.method == "POST":
        title = request.form["title"]
        content = request.form["content"]
        post = {
            "title": title,
            "About" : content,
            "manager": session["email"],
            "time" : str(datetime.datetime.now())

        }
        try:
        #print(title, content, file=sys.stderr)
        #push the post object to the database
            db.child("Communities").push(post)
            return redirect("/")
        except:
            return render_template("create_community", message= "Something wrong happened", news=news)
    
    return render_template("create_community.html")

@app.route("/my_feed", methods=["GET", "POST"])
@isAuthenticated
def my_feed():
    communities = db.child("Communities").get()
    posts = db.child("Posts").get()
    news_posts = db.child("News_posts").get()
    user = session['usr']
    return render_template("my_feed.html", posts=posts, news_posts=news_posts, user=session['usr'],communities=communities)
@app.route("/blog", methods=["GET", "POST"])
def blog():
    return render_template("blog.html")
@app.route("/community_area/<id>", methods=["GET","POST","LIKE"])
def community_area(id):
    orderedDict =  db.child("Communities").order_by_key().equal_to(id).limit_to_first(1).get()
    posts = db.child("Posts").get()
    news = db.child("News_posts").get()
    if request.method == "POST":
        account = db.child("Accounts").get()
        user_key = ""
        for a in account:
            print(a)
            if a.val().email == session["email"]:
                user_key = a.key()
        post = {
            "Subscriber": session['usr']
        }
        try:
            db.child("Account/"+user_key+"/subscriptions/").push(post)
            return redirect("/")
        except:
            return render_template("community_area.html", data=orderedDict, posts = posts, storage=storage, id=id, news=news)
    
    return render_template("community_area.html", data=orderedDict, posts = posts, storage=storage, id=id, news=news)

@app.route("/post/<id>", methods=["GET","POST","LIKE"])
def post(id):
    if request.method == "POST":
        print("comments")
        comment1 = request.form["comment_"]
        comments12 = {
            "comment":comment1,
            "post id" : id,
            "time" : str(datetime.datetime.now())
            }
        try:
            print("pushing comments")
            db.child("Posts/"+id+"/Comments").push(comments12)
            return redirect("/post/" + id)
        except:
             return render_template("/post/" + id, message= "Something wrong happened")

    allcomments = db.child("Posts/"+id+"/Comments").get()

    orderedDict = db.child("Posts").order_by_key().equal_to(id).limit_to_first(1).get()
    print(orderedDict, file=sys.stderr)

    links = storage.child(id).get_url(None)

    if allcomments.val() == None:
          #print(posts, file=sys.stderr)
          return render_template("post.html", data=orderedDict, l=links, id=id, storage=storage)

    return render_template("post.html", comments= allcomments,data=orderedDict, l=links, id=id, storage=storage)

@app.route("/edit/<id>", methods=["GET", "POST"])
def edit(id):
    if request.method == "POST":
      title = request.form["title"]
      content = request.form["content"]

      post = {
        "title": title,
        "content": content,
        "author": session["email"]

      }

      #update the post
      db.child("Posts").child(id).update(post)
      return redirect("/post/" + id)


    orderedDict =  db.child("Posts").order_by_key().equal_to(id).limit_to_first(1).get()
    return render_template("edit.html", data=orderedDict)

@app.route("/delete/<id>", methods=["POST"])
def delete(id):
    db.child("Posts").child(id).remove()
    return redirect("/")


#run the main script
if __name__ == "__main__":
    app.run(debug=True)
    http_server = WSGIServer(('0.0.0.0', 5000), app)
    http_server.serve_forever()
