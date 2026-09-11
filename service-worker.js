"use strict";


const CACHE_NAME =

"LainoLive-cache-v1";



const APP_FILES = [


"/",

"/index.html",

"/login.html",

"/profile.html",

"/settings.html",

"/live.html",

"/viewer.html",


"/app.js",

"/chat.js",

"/streams-cache.js",

"/live-webrtc.js",

"/viewer-webrtc.js",


"/manifest.json"


];







self.addEventListener(

"install",

event => {


event.waitUntil(


caches.open(

CACHE_NAME

)

.then(

cache => {


return cache.addAll(

APP_FILES

);


}

)

);


}

);








self.addEventListener(

"activate",

event => {


event.waitUntil(


caches.keys()

.then(

keys => {


return Promise.all(

keys.map(

key => {


if(

key !== CACHE_NAME

){


return caches.delete(

key

);


}


}

)

);


}

)

);


}

);









self.addEventListener(

"fetch",

event => {



event.respondWith(


caches.match(

event.request

)

.then(

cached => {


if(cached){


return cached;


}




return fetch(

event.request

)

.then(

response => {



return response;


}

)

.catch(

()=>{


return caches.match(

"/index.html"

);


}

);



}

)

);



}

);