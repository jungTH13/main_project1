import requests
import bs4
import sqlite3
import datetime
import os
import urllib
import json
import pandas as pd
DB_FILENAME = 'property.db'
DB_FILEPATH = os.path.join(os.getcwd(), DB_FILENAME)
#from app import DB_FILEPATH

global row,coordinate

#자치구코드 설정(서울 자치구리스트)
SGG_CD=[11110,11140,11170,11200,11215,11230,11260,11290,11305,11320,11350,11380,11410,11440,11470,11500,11530,11545,11560,11590,11620,11650,11680,11710,11740]
SGG_NM=["종로구","중구","용산구","성동구","광진구","동대문구","중랑구","성북구","강북구","도봉구","노원구","은평구","서대문구","마포구","양천구","강서구","구로구","금천구","영등포구","동작구","관악구","서초구","강남구","송파구","강동구"]
#건물명의 경우 매매건물유형에 따라 명칭이 달라짐으로 코드내에서 따로 표기
COLUMNS=['거래금액','년','월','일','건축년도','전용면적','법정동','지번','층','지역코드']
B_NAME=['단지','연립다세대','아파트']
NUM=24 #업데이트 범위설정(월단위),테이블내 데이터가 없을시 NUM개월정보까지 업데이트
API_NAME=['아파트','연립다세대','오피스텔']
TRIGER=False

#날자 정보를 담은 변수
DAY=datetime.datetime.now().day
MONTH=datetime.datetime.now().month
YEAR=datetime.datetime.now().year

#naver cloud platform Geocoding 주소->좌표값 출력 함수
def search_map(search_text):
    client_id = 'yrmv6xu634' #클라이언트 ID값
    client_secret = 'b7zTPTfLe4y96bmeIp1vuBdd2Y8yAWf0hIen3akG' #클라이언트 Secret값
    encText = urllib.parse.quote(search_text) 
    url = 'https://naveropenapi.apigw.ntruss.com/map-geocode/v2/geocode?query='+encText
    
    for i in range(10):#API 정보 호출에서 에러 발생시 10회까지 재시도
        try:
            request = urllib.request.Request(url)
            request.add_header('X-NCP-APIGW-API-KEY-ID', client_id)
            request.add_header('X-NCP-APIGW-API-KEY', client_secret)
            response = urllib.request.urlopen(request)
            rescode = response.getcode()
        except Exception as ex:
            print(f"Geo API 에러발생 재시도({i+1}/10) / 에러내용: {ex}")
            if i+1==10:#재시도 횟수를 초과시 critical error전환
                raise Exception(ex)
            continue
        break
                
    if(rescode==200):
        response_body = response.read()
        address=json.loads(response_body.decode('utf-8'))
        try:
          return {'x':address.get('addresses')[0].get('x'),'y':address.get('addresses')[0].get('y')}
        except:
          return {'x':0.0,'y':0.0}
    else:
        print("Error Code:" + rescode)

def create_table(cur,conn,NAME):
  #부동산 실거래가 정보 테이블 생성
  cur.execute(f"""CREATE TABLE IF NOT EXISTS {NAME}(
                                                  번호 INT,
                                                  거래금액 INT,
                                                  년 INT, 
                                                  월 INT,
                                                  일 INT,
                                                  건축년도 INT,
                                                  전용면적 FLOAT,
                                                  대지면적 FLOAT,
                                                  법정동 VARCHAR,
                                                  지번 VARCHAR,
                                                  층 INT,
                                                  지역코드 INT,
                                                  건물용도 VARCHAR,
                                                  건물명 VARCHAR,
                                                  x FLOAT,
                                                  y FLOAT,
                                                  이후거래가격 INT,
                                                  이후거래개월수 INT,
                                                  이전거래가격 INT
                                                  )
                                                  """)
  conn.commit()

#API 정보를 받아오기위한 날짜 인자 개산을 위한 함수
def MONTH_set(YEAR,MONTH,num):
  MONTH-=num
  while MONTH<1:
    YEAR=YEAR - 1
    MONTH+=12

  if MONTH<10:
    MONTH='0'+str(MONTH)
  
  return f"{YEAR}{MONTH}"


#데이터를 저장할 데이터 베이스 생성
conn=sqlite3.connect(DB_FILEPATH) 
cur=conn.cursor()
#테이블 생성 함수 호출
create_table(cur,conn,'seoul')

#가장 최근 데이터의 날짜 정보를 검색
recent_YM=cur.execute("""select 년,월 from seoul order by 년 DESC,월 DESC limit 1""").fetchall()
print(recent_YM)
if len(recent_YM)==1: #데이블내에 데이터가 존재시 가장 최근 정보로부터 3개월전의 데이터까지 업데이트
    set_YEAR=YEAR-recent_YM[0][0]
    set_MONTH=MONTH-recent_YM[0][1]
    NUM=set_YEAR*12+set_MONTH+3
    print(f"현재 달에서 {NUM}개월까지의 정보를 업데이트 시작")
else:
    print(f"데이터베이스가 비어있기때문에 현재 달에서 {NUM}개월까지의 정보를 업데이트 시작")



url = ['http://openapi.molit.go.kr:8081/OpenAPI_ToolInstallPackage/service/rest/RTMSOBJSvc/getRTMSDataSvcAptTrade', # 아파트 실거래 API
       'http://openapi.molit.go.kr:8081/OpenAPI_ToolInstallPackage/service/rest/RTMSOBJSvc/getRTMSDataSvcRHTrade', # 연립다세대 실거래 API
       #'http://openapi.molit.go.kr:8081/OpenAPI_ToolInstallPackage/service/rest/RTMSOBJSvc/getRTMSDataSvcSHTrade', # 단독다가구 실거래 API
       'http://openapi.molit.go.kr/OpenAPI_ToolInstallPackage/service/rest/RTMSOBJSvc/getRTMSDataSvcOffiTrade' # 오피스텔 실거래 API
       ]
serviceKey='G5PNa/g6JgL1Lm5mxT/qzJwHk6wx66pyiYtTOkiJ/icsoCs/5cL7c3ILtaDLP6eTOt7OSK7a88jixLBzSTCdOw=='


#업데이트할 달의 정보를 제거
cur.execute(f"""delete from seoul where 년>={YEAR} and 월>{MONTH-NUM} """)
count=-1
try:
    #번호 인덱싱을 위한 DB내 가장큰 번호를 확인
    index_num=cur.execute("select 번호 from seoul order by 번호 DESC limit 1").fetchone()
    if index_num==None:
        index_num=1
    else:
        index_num=index_num[0]+1

    for link in url: #건물용도에 대한 실거래 정보 조회
        count+=1
        for LAWD_CD in SGG_CD: #법정동리스트
            for num in range(NUM): #가장 최근에서 NUM의 개월수만큼의 이전 정보 업데이트
                params ={'serviceKey' : serviceKey, 'LAWD_CD' : LAWD_CD, 'DEAL_YMD' : f'{MONTH_set(YEAR,MONTH,num)}' }
                
                for i in range(10):#API 정보 호출에서 에러 발생시 10회까지 재시도
                    try:
                        response = requests.get(link, params=params)
                        status=response.status_code
                    except Exception as ex:
                        print(f"실거래 API 에러발생 재시도({i+1}/10) / 에러내용: {ex}")
                        if i+1==10:#재시도 횟수를 초과시 critical error전환
                            raise Exception(ex)
                        continue
                    break
                print(f"{API_NAME[count]}/{LAWD_CD}/{MONTH_set(YEAR,MONTH,num)}",end='  ')
                
                if status==200:
                    #API를 통해 받아온 XML 정보를 파싱
                    parsed_data=bs4.BeautifulSoup(response.text, 'lxml-xml')
                    
                    #받아온 정보에서 이상발생여부 확인 및 개수 확인
                    if parsed_data.find('totalCount'):
                        print('count:'+parsed_data.find('totalCount').text)
                    else:
                        print(parsed_data.text)
                        TRIGER=True
                        break
                    
                    DEAL_data=parsed_data.find_all('item')
                    if DEAL_data != None:
                    #거래건수 별 데이터 확인
                        for d in DEAL_data:
                            row=d
                            #거래건내의 정보 확인
                            result = [row.find(i).text if row.find(i) else 0 for i in COLUMNS ]
                            result.extend([[i,row.find(i).text] if i!='단지' else ['오피스텔',row.find(i).text] for i in B_NAME if row.find(i)])
                            result.append([float(row.find(i).text) if row.find(i) else 0 for i in ['대지면적','대지권면적']])
                            coordinate=search_map(f"서울특별시 {result[6]} {result[7]}")
                            cur.execute(f"""INSERT INTO seoul VALUES({index_num},{result[0].replace(' ','').replace(',','')},{result[1]},{result[2]},{result[3]},{result[4]},{result[5]},{max(result[11])},"{result[6]}","{result[7]}",{result[8]},{result[9]},"{result[10][0]}","{result[10][1]}",{coordinate['y']},{coordinate['x']},0,0,0)""")
                            index_num+=1
                        conn.commit()
                else:
                    print("UPDATE ERROR(API can't connected)")
                    TRIGER=True
                    break
                if TRIGER:
                    break
            if TRIGER:
                break
        if TRIGER:
            break
except Exception as ex:
    print('***critical error***')
    print(ex)
    TRIGER=True
    
if TRIGER:
    print("데이터베이스 롤백")
    conn.rollback()
else:
    print("데이터베이스 적용 완료")
    conn.commit()
    
data=cur.execute("select * from seoul where 이후거래가격=0 and 이전거래가격=0").fetchall()
print(f"전처리 진행({len(data)}건)")
for d in data:
    if d[0]%1000==0:
        print(f"{d[0]}/{len(data)}")
    searched_d=cur.execute(f"""select * from seoul where 법정동='{d[8]}' and 건물명="{d[13]}" and 전용면적='{d[6]}' order by 년 DESC,월 DESC, 일 DESC""").fetchall()
    if len(searched_d)>1:
        count=False
        for s_d in searched_d:
            if sum(s_d[16:])==0:
                count=True
                break
        if count:
            for i in range(len(searched_d)):
                if i==0:
                    cur.execute(f"update seoul set 이전거래가격 = {searched_d[i+1][1]} where 번호={searched_d[i][0]}")
                elif i==len(searched_d)-1:
                    set_MONTH=(searched_d[i-1][2]-searched_d[i][2])*12+searched_d[i-1][3]-searched_d[i][3]
                    cur.execute(f"update seoul set 이후거래가격 = {searched_d[i-1][1]} where 번호={searched_d[i][0]}")
                    cur.execute(f"update seoul set 이후거래개월수 = {set_MONTH} where 번호={searched_d[i][0]}")
                else:
                    cur.execute(f"update seoul set 이전거래가격 = {searched_d[i+1][1]} where 번호={searched_d[i][0]}")
                    set_MONTH=(searched_d[i-1][2]-searched_d[i][2])*12+searched_d[i-1][3]-searched_d[i][3]
                    cur.execute(f"update seoul set 이후거래가격 = {searched_d[i-1][1]} where 번호={searched_d[i][0]}")
                    cur.execute(f"update seoul set 이후거래개월수 = {set_MONTH} where 번호={searched_d[i][0]}")
conn.commit()
print(f"전처리 완료({len(data)}건)")
cur.close()
conn.close()

