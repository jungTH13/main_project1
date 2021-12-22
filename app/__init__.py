from flask import Flask
import os
from apscheduler.schedulers.background import BackgroundScheduler
import datetime
import urllib
import json

DB_FILENAME = 'property.db'
DB_FILEPATH = os.path.join(os.getcwd(), DB_FILENAME)


def create_app():
    app=Flask(__name__)
    
    from app.views.main import main
    
    app.register_blueprint(main)
    
    return app
    
def update():
    print("update start")
    exec(open(os.path.join(os.getcwd(), 'app/data/make_DB.py'),'rt',encoding='UTF8').read())
    print("update complite")
    
if __name__=='__main__':
    app.run(debug=True)
    app.config['JSON_AS_ASCII'] = False

#스케쥴러의 자동업데이트 시간을 설정하기위한 시간정보 저장 및 불러오기
try:
    update_time=open("scheduler_time.txt","r+")
except:
    update_time=open("scheduler_time.txt","w")
    set_hour=datetime.datetime.now().hour
    set_min=datetime.datetime.now().minute+1
    if set_min>=60:
        set_min-=60
        set_hour+=1
        if set_hour>=24:
            set_hour-=24
    update_time.write(str(set_hour)+':'+str(set_min))
    update_time.close()
    update_time=open("scheduler_time.txt","r")

update_time=update_time.readline()
update_time=str(update_time).split(':')
print(f"daily Scheduler set time {update_time[0]}:{update_time[1]}")

#스케쥴러 설정
scheduler= BackgroundScheduler()
try:
    job= scheduler.add_job(update, 'cron', day_of_week='mon-sun', hour=int(update_time[0]), minute=int(update_time[1]))
except Exception as error:
    print('오류발생:',error)
scheduler.start()

