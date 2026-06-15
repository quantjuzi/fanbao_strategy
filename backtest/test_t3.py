
import sys,io
sys.stdout=io.TextIOWrapper(sys.stdout.buffer,encoding='utf-8')
import pandas as pd,numpy as np

CSV=r'.\data\全市场A股_2026-04-12_2026-06-12.csv'
df=pd.read_csv(CSV)
df['index']=pd.to_datetime(df['index'])
df.sort_values(['证券代码','index'],inplace=True)
df['M7']=df.groupby('证券代码')['close'].transform(lambda x:x.rolling(7).mean())
df['M14']=df.groupby('证券代码')['close'].transform(lambda x:x.rolling(14).mean())
df['zt_Tm2']=df.groupby('证券代码')['是否涨停'].shift(1)
df['zt_Tm3']=df.groupby('证券代码')['是否涨停'].shift(2)

def bt(cond):
    df['sig']=cond.astype(int)
    r=[]
    for _,row in df[df['sig']==1].iterrows():
        c=row['证券代码'];t1=row['index']
        td=df[(df['证券代码']==c)&(df['index']>t1)]
        if td.empty:continue
        bp=td.iloc[0]['open']
        tp1=df[(df['证券代码']==c)&(df['index']>td.iloc[0]['index'])]
        if tp1.empty:continue
        r.append((tp1.iloc[0]['close']-bp)/bp*100)
    return r

base=(df['zt_Tm2']==1)&(df['是否涨停']==0)&(df['money']>1.5e9)&(df['M7']/df['M14']>1)&df['M14'].notna()
t3=(df['zt_Tm2']==1)&(df['zt_Tm3']==1)&(df['是否涨停']==0)&(df['money']>1.5e9)&(df['M7']/df['M14']>1)&df['M14'].notna()

print(f'{"基础(15亿)":<12} 信号{len(bt(base)):>4}',end='')
p=bt(base); w=sum(1 for x in p if x>0)
print(f' 胜率{w/len(p)*100:5.1f}% 平均{np.mean(p):+.2f}% 最大赚{max(p):+.2f}% 最大亏{min(p):+.2f}%')

p2=bt(t3); w2=sum(1 for x in p2 if x>0)
print(f'{"+T-3涨停":<12} 信号{len(p2):>4} 胜率{w2/len(p2)*100:5.1f}% 平均{np.mean(p2):+.2f}% 最大赚{max(p2):+.2f}% 最大亏{min(p2):+.2f}%')
