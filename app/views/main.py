from flask import Blueprint, render_template, request,jsonify
import sqlite3
from urllib import parse
from app import DB_FILEPATH
import json
import pandas as pd
from category_encoders import OrdinalEncoder
import pickle
import os
from xgboost import XGBRegressor
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import Input, Dense, BatchNormalization, LeakyReLU


main=Blueprint('main',__name__)


COLUMNS=['번호','거래금액','년','월','일','건축년도','전용면적','대지면적','법정동','지번','층','지역코드','건물용도','건물명','x','y','이후거래가격','이후거래개월수','이전거래가격']
col_select=['거래금액','년','월','일','건축년도','전용면적','대지면적','법정동','지번','층','지역코드','건물용도','건물명','x','y','이후거래가격','이후거래개월수','이전거래가격']
data_base="(SELECT * FROM seoul s order by 년 DESC,월 DESC,일 DESC)"

@main.route('/')
def index3():
    conn=sqlite3.connect(DB_FILEPATH) 
    cur=conn.cursor()
    data=cur.execute(f"select * from {data_base} limit 10").fetchall()
    data_list=[]
    for d in data:
        data_dic={}
        for c,d in zip(COLUMNS,d):
            data_dic[c]=d

        if data_dic['거래금액']//10000:
            if data_dic['거래금액']%10000:
                data_dic['거래금액']=f"{data_dic['거래금액']//10000}억{data_dic['거래금액']%10000}만원"
            else:
                data_dic['거래금액']=f"{data_dic['거래금액']//10000}억"
        else:
            data_dic['거래금액']=f"{data_dic['거래금액']}만원"
        data_list.append(data_dic)
    
    
    return render_template('index.html',data=data_list,count=len(data_list),start=0)

@main.route('/searching')
def search():
    conn=sqlite3.connect(DB_FILEPATH) 
    cur=conn.cursor()
    data=cur.execute(f"select * from {data_base} order by 년 DESC,월 DESC,일 DESC limit  1000").fetchall()
    print(f"select {','.join(col_select)} from {data_base} order by 년 DESC,월 DESC,일 DESC limit 1000")
    search_list=[]
    data_str_list=[]
    
    for d in cur.execute(f"SELECT DISTINCT 법정동 from {data_base} s order by 법정동").fetchall():
        search_list.append(d[0])
    
    for d in data:
        data_dic={}
        for c,d in zip(COLUMNS,d):
            if c=='건물명':
                d=d.replace('\t','')
            data_dic[c]=d
            
        

        if data_dic['거래금액']//10000:
            if data_dic['거래금액']%10000:
                data_dic['거래금액']=f"{data_dic['거래금액']//10000}억{data_dic['거래금액']%10000}만원"
            else:
                data_dic['거래금액']=f"{data_dic['거래금액']//10000}억"
        else:
            data_dic['거래금액']=f"{data_dic['거래금액']}만원"
        data_str_list.append(f"{data_dic}")
    print(">>>",data_str_list[36])
    return render_template('searching.html',data_str=('|'.join(data_str_list)),search_list=('|'.join(search_list)))

@main.route('/searching_db',methods=['POST'])
def search_db():
    conn=sqlite3.connect(DB_FILEPATH) 
    cur=conn.cursor()
    
    data={
        '법정동':request.form['1'],
        '건물용도':request.form['2'],
        '거래가이상':request.form['3'],
        '거래가이하':request.form['4'],
        '건물명':request.form['5']
    }
    start_sql=f"select {','.join(col_select)}, count(전용면적) from {data_base} "
    sql=[]
    end_sql=' GROUP by 건물명,전용면적 order by 년 DESC,월 DESC,일 DESC'
    if data['법정동']!='전체':
        sql.append(f"법정동='{data['법정동']}'")
    if data['건물용도']!='전체':
        sql.append(f"건물용도 = '{data['건물용도']}'")
    if data['거래가이상']!='':
        sql.append(f"거래금액 >= {data['거래가이상']}")
    if data['거래가이하']!='':
        sql.append(f"거래금액 <= {data['거래가이하']}")
    if data['건물명']!='':
        sql.append(f"건물명 = '{data['건물명']}'")
        
    if len(sql):
        sql='where '+' and '.join(sql)
        sql=start_sql + sql + end_sql+" limit 1000"
    else:
        sql=start_sql + end_sql+" limit 3000"
    print("DB 호출 sql:",sql)
    data=cur.execute(sql).fetchall()
    deal=[]
    for d in data:
        if d[0]//10000:
            if d[0]%10000:
                deal.append(f"{d[0]//10000}억{d[0]%10000}만원")
            else:
                deal.append(f"{d[0]//10000}억")
        else:
            deal.append(f"{d[0]}만원")
            
    print(f"map_data: select {','.join(col_select)} from ({sql}) group by x,y order by 년 DESC,월 DESC,일 DESC")    
    map_data=cur.execute(f"select x,y,건물명,전용면적,거래금액,이전거래가격 from ({sql}) group by x,y order by 년 DESC,월 DESC,일 DESC").fetchall()
    
    return {"data":data,'map_data':map_data,'deal':deal},200


@main.route('/reports')
def reports():
    return render_template('/reports.html')

@main.route('/reports_db',methods=['POST'])
def reports_db():
    conn=sqlite3.connect(DB_FILEPATH) 
    cur=conn.cursor()
    
    data={
        '자치구':request.form['1'],
        '건물용도':request.form['2'],
        '실거래시작일':request.form['3'],
        '실거래종료일':request.form['4']
    }
    
    print("요청된 조건:",data)
    #그래프 1 sql
    results_dataset=[]
    map_dataset="" #map데이터 추출을 위한 조건문 저장 변수
    
    for set_sql in ['avg(거래금액/(전용면적/3.3))','count(거래금액)']:
        data1={0:'',1:[],2:'',3:'',4:'',5:''}#반환할 json(dic)형태의 변수(0:년월라벨,1:전체통계,2:선택통계,3:자치구)
        #기본 전체데이터의 비교용 sql문(sql0) 생성 및 입력된 조건에 따른 sql문 생성(sql1)
        if data['자치구']=='' and data['건물용도']=='':
            set_date=[]
            if data['실거래시작일']!='':
                set_date.append(f"년*10000+월*100+일>={data['실거래시작일'].replace('-','')}")
            if data['실거래종료일']!='':
                set_date.append(f"년*10000+월*100+일<={data['실거래종료일'].replace('-','')}")
            if len(set_date):
                set_date=[' where '+' and '.join(set_date),' and '+' and '.join(set_date)]
            else:
                set_date=['','']
                
            sql_f=[f"select 년,월,{set_sql} from {data_base}{set_date[0]} group by 년,월",
                f"select 년,월,{set_sql} from {data_base} where 건물용도='아파트'{set_date[1]} group by 년,월",
                f"select 년,월,{set_sql} from {data_base} where 건물용도='오피스텔'{set_date[1]} group by 년,월",
                f"select 년,월,{set_sql} from {data_base} where 건물용도='연립다세대'{set_date[1]} group by 년,월"]
            data1[1]=[1,2,3]
            map_dataset=[set_date[0].replace('where','')]
        else:
            sql0_start=f"select 년,월,{set_sql} from {data_base} "
            sql0=[]
            sql0_end=" group by 년,월"
            
            sql1_start=f'select 년,월,{set_sql} from {data_base} where '
            sql1=[]
            sql1_end=' group by 년,월'
            if data['자치구'] != '':
                sql1.append(f"지역코드='{data['자치구']}'")
                data1[1].append(int(data['자치구']))
            if data['건물용도'] !='':
                sql1.append(f"건물용도='{data['건물용도']}'")
                if data['자치구'] == '':
                    buf={'아파트':1,'오피스텔':2,'연립다세대':3}
                    data1[1].append(buf[data['건물용도']])
            if data['실거래시작일']:
                sql1.append(f"년*10000+월*100+일>={data['실거래시작일'].replace('-','')}")
                sql0.append(f"년*10000+월*100+일>={data['실거래시작일'].replace('-','')}")
            if data['실거래종료일']:
                sql1.append(f"년*10000+월*100+일<={data['실거래종료일'].replace('-','')}")
                sql0.append(f"년*10000+월*100+일<={data['실거래종료일'].replace('-','')}")
            
            if len(sql0)!=0:
                sql0_start+='where '
            sql_f=[sql0_start+' and '.join(sql0)+sql0_end, sql1_start+' and '.join(sql1)+sql1_end]
            map_dataset=sql1
        print("DB 호출 sql:",sql_f)
        
        #생성된 sql문(1~4개)에 따른 데이터 검색 및 리스트화(0:년월,1:자치구(전체시 건물용도),2~5:데이터) 
        for n in range(len(sql_f)):
            results=cur.execute(sql_f[n]).fetchall()
            results_data=[]
            results_date=[]
            for row in results:
                if row[1]<10:
                    date_str=f"0{row[1]}"
                else:
                    date_str=row[1]
                results_date.append(f"{row[0]}/{date_str}")
                results_data.append(int(row[2]))
            data1[0]=results_date
            data1[n+2]=results_data
            
        #데이터의 길이를 요청 sql길이 맞추어 조정
        if len(data1[2])!=0:
            data1[1]=data1[1][:len(data1[2])]
        for d in data1:
            print(data1[d])
        results_dataset.append(data1)

    #map 표시 매물들의 좌표 및 등락폭 정보 추출   
    if len(map_dataset)!=0 and map_dataset[0]!='':
        print("map_data 호출 sql:",f"select x,y,거래금액,이전거래가격 from {data_base} where 이전거래가격>0 and {' and '.join(map_dataset)} group by x,y order by 년 DESC,월 DESC,일 DESC")
        map_dataset=cur.execute(f"select x,y,거래금액,이전거래가격 from {data_base} where 이전거래가격>0 and {' and '.join(map_dataset)} group by x,y order by 년 DESC,월 DESC,일 DESC").fetchall()
    else:
        print("map_data 호출 sql:",f"select x,y,거래금액,이전거래가격 from {data_base} where 이전거래가격>0 group by x,y order by 년 DESC,월 DESC,일 DESC")
        map_dataset=cur.execute(f"select x,y,거래금액,이전거래가격 from {data_base} where 이전거래가격>0 group by x,y order by 년 DESC,월 DESC,일 DESC").fetchall()
    print("maker count:",len(map_dataset),"(limit: 3000)")
    return {"data_set":results_dataset,"map_data_set":map_dataset[:3000]}

@main.route('/test')
def test():
    return render_template('/test.html')

@main.route('/api')
def api():
    return render_template('/api.html')

@main.route('/api_SGG',methods=['POST'])
def SGG_info():
    conn=sqlite3.connect(DB_FILEPATH) 
    cur=conn.cursor()
    info=request.form['info']
    if info=="법정동":
        SGG_CD=request.form['1']
        data=cur.execute(f"select DISTINCT 법정동 from {data_base} where 지역코드={SGG_CD} order by 법정동").fetchall()
        print(data)
        return {"법정동":data}
    elif info=="건물명":
        data=cur.execute(f"select DISTINCT 건물명 from {data_base} where 지역코드={request.form['1']} and 법정동='{request.form['2']}' and 건물용도='{request.form['3']}' order by 건물명").fetchall()
        print(f"select DISTINCT 건물명 from {data_base} where 지역코드={request.form['1']} and 법정동='{request.form['2']}' and 건물용도='{request.form['3']}' order by 건물명")
        return {"건물명":data}
    elif info=="검색":
        data=cur.execute(f"""select * from {data_base} where 지역코드={request.form['1']} and 법정동='{request.form['2']}' and 건물용도='{request.form['3']}' and 건물명="{request.form['4']}" group by 법정동,건물명,전용면적,층 order by 년 DESC,월 DESC, 일 DESC""").fetchall()
        print(f"""select * from {data_base} where 지역코드={request.form['1']} and 법정동='{request.form['2']}' and 건물용도='{request.form['3']}' and 건물명="{request.form['4']}" group by 법정동,건물명,전용면적,층 order by 년 DESC,월 DESC, 일 DESC""")
        return {"검색":data}
    elif info=="예측":
        select_name=['년','월','일','거래금액', '건축년도', '전용면적', '대지면적', '법정동', '층', '지역코드', '건물용도', 'x', 'y','이후거래개월수', '이전거래가격']
        data=cur.execute(f"""select {','.join(select_name)} from {data_base} where 지역코드={request.form['1']} and 법정동='{request.form['2']}' and 건물용도='{request.form['3']}' and 건물명="{request.form['4']}" group by 법정동,건물명,전용면적,층 order by 년 DESC,월 DESC, 일 DESC""").fetchall()
        print(f"""select {','.join(select_name)} from {data_base} where 지역코드={request.form['1']} and 법정동='{request.form['2']}' and 건물용도='{request.form['3']}' and 건물명="{request.form['4']}" group by 법정동,건물명,전용면적,층 order by 년 DESC,월 DESC, 일 DESC""")
        
        results=pred_deal(data,select_name,request.form['5'])
        
        return {'XG':results[0].tolist(),'ANN':results[1].tolist()} #0 -> 원본 :results[1].tolist()
        
        
        
def pred_deal(data,columns,MONTH):
    with open('ord_mapping_data.pkl','rb') as f:
        ord_mapping_data=pickle.load(f)
    
    #XG모델 호출
    encoder=OrdinalEncoder(mapping=ord_mapping_data,cols=['법정동','지역코드','건물용도'])
    df=pd.DataFrame(data,columns=columns)
    df['이후거래개월수']=int(MONTH)
    df['날짜']=df['년']*10000+df['월']*100+df['일']
    pred_df=df.drop(['년','월','일'],axis=1)
    pred_df=encoder.fit_transform(pred_df)
    model=XGBRegressor(n_estimators=500,seed=1,min_child_weight=8,max_depth=10,learning_rate=0.08,gamma=0.25,colsample_bytree=0.95)
    model.load_model('XGBoost.model')
    pred_data=model.predict(pred_df)
    
    #ANN모델 호출
    pred_df=pred_df.to_numpy().astype('float32')
    
    model=Sequential()
    model.add(Input(13))
    model.add(BatchNormalization())
    model.add(Dense(32,activation=LeakyReLU()))
    model.add(BatchNormalization())
    model.add(Dense(64,activation=LeakyReLU()))
    model.add(BatchNormalization())
    model.add(Dense(128,activation=LeakyReLU()))
    model.add(BatchNormalization())
    model.add(Dense(32,activation=LeakyReLU()))
    model.add(Dense(1,activation=LeakyReLU()))
    
    model.load_weights('ANN.hdf5')
    pred_data2=model.predict(pred_df)

    
    return (pred_data.astype(int),pred_data2[:,0].astype(int))#용량 설정으로 ANN 제거/ 0-> 원본: pred_data2[:,0].astype(int)