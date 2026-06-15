
import sys,io
sys.stdout=io.TextIOWrapper(sys.stdout.buffer,encoding='utf-8')
import pandas as pd,numpy as np

CSV=r'C:\Users\Administrator\Desktop\全市场A股_2026-04-12_2026-06-12.csv'
df0=pd.read_csv(CSV)
df0['index']=pd.to_datetime(df0['index'])
df0.sort_values(['证券代码','index'],inplace=True)
df0['M7']=df0.groupby('证券代码')['close'].transform(lambda x:x.rolling(7).mean())
df0['M14']=df0.groupby('证券代码')['close'].transform(lambda x:x.rolling(14).mean())
df0['zt_Tm2']=df0.groupby('证券代码')['是否涨停'].shift(1)
df0['zt_Tm3']=df0.groupby('证券代码')['是否涨停'].shift(2)

def bt(df,cond):
    df['sig']=cond.astype(int)
    r=[]
    for _,row in df[df['sig']==1].iterrows():
        c=row['证券代码'];t1=row['index']
        td=df[(df['证券代码']==c)&(df['index']>t1)]
        if td.empty:continue
        td2=df[(df['证券代码']==c)&(df['index']>td.iloc[0]['index'])]
        if td2.empty:continue
        r.append((td2.iloc[0]['close']-td.iloc[0]['open'])/td.iloc[0]['open']*100)
    return r

tests=[]
b=(df0['zt_Tm2']==1)&(df0['是否涨停']==0)&(df0['money']>1.5e9)&(df0['M7']/df0['M14']>1)&df0['M14'].notna()
tests.append(('基准(15亿,M7>1)',bt(df0,b)))

c1=(df0['zt_Tm2']==1)&(df0['是否涨停']==0)&(df0['money']>1e9)&(df0['M7']/df0['M14']>1)&df0['M14'].notna()
tests.append(('成交额>10亿',bt(df0,c1)))

c2=(df0['zt_Tm2']==1)&(df0['是否涨停']==0)&(df0['money']>2e9)&(df0['M7']/df0['M14']>1)&df0['M14'].notna()
tests.append(('成交额>20亿',bt(df0,c2)))

c3=(df0['zt_Tm2']==1)&(df0['是否涨停']==0)&(df0['money']>3e9)&(df0['M7']/df0['M14']>1)&df0['M14'].notna()
tests.append(('成交额>30亿',bt(df0,c3)))

c4=(df0['zt_Tm2']==1)&(df0['是否涨停']==0)&(df0['money']>1.5e9)&(df0['M7']/df0['M14']>1.05)&df0['M14'].notna()
tests.append(('M7/M14>1.05',bt(df0,c4)))

c5=(df0['zt_Tm2']==1)&(df0['是否涨停']==0)&(df0['money']>1.5e9)&(df0['M7']/df0['M14']>1.1)&df0['M14'].notna()
tests.append(('M7/M14>1.1',bt(df0,c5)))

c6=(df0['zt_Tm2']==1)&(df0['zt_Tm3']==1)&(df0['是否涨停']==0)&(df0['money']>1.5e9)&(df0['M7']/df0['M14']>1)&df0['M14'].notna()
tests.append(('T-3也涨停(连2板)',bt(df0,c6)))

c7=(df0['zt_Tm2']==1)&(df0['zt_Tm3']==1)&(df0['是否涨停']==0)&(df0['money']>3e9)&(df0['M7']/df0['M14']>1)&df0['M14'].notna()
tests.append(('连板+30亿',bt(df0,c7)))

print('='*60)
print(f'{"测试项":<16} {"信号数":>6} {"胜率":>8} {"平均":>10}')
print('='*60)
for n,t in tests:
    if t:
        w=sum(1 for x in t if x>0)
        print(f'{n:<16} {len(t):>6} {w/len(t)*100:>7.1f}% {np.mean(t):>+9.2f}%')
    else:
        print(f'{n:<16} 无信号')
