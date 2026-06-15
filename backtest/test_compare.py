
import sys,io
sys.stdout=io.TextIOWrapper(sys.stdout.buffer,encoding='utf-8')
import pandas as pd,numpy as np

CSV=r'.\data\全市场A股_2026-04-12_2026-06-12.csv'
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
        bp=td.iloc[0]['open']
        tp1=df[(df['证券代码']==c)&(df['index']>td.iloc[0]['index'])]
        if tp1.empty:continue
        r.append((tp1.iloc[0]['close']-bp)/bp*100)
    return r

b=df0
base=(b['zt_Tm2']==1)&(b['是否涨停']==0)&(b['money']>1.5e9)&(b['M7']/b['M14']>1)&b['M14'].notna()

tests=[('基准(15亿,M7>1)',bt(b,base))]
tests.append(('成交额>10亿',bt(b,(b['zt_Tm2']==1)&(b['是否涨停']==0)&(b['money']>1e9)&(b['M7']/b['M14']>1)&b['M14'].notna())))
tests.append(('成交额>20亿',bt(b,(b['zt_Tm2']==1)&(b['是否涨停']==0)&(b['money']>2e9)&(b['M7']/b['M14']>1)&b['M14'].notna())))
tests.append(('成交额>30亿',bt(b,(b['zt_Tm2']==1)&(b['是否涨停']==0)&(b['money']>3e9)&(b['M7']/b['M14']>1)&b['M14'].notna())))
tests.append(('T-3涨停(连2板)',bt(b,(b['zt_Tm2']==1)&(b['zt_Tm3']==1)&(b['是否涨停']==0)&(b['money']>1.5e9)&(b['M7']/b['M14']>1)&b['M14'].notna())))
tests.append(('连2板+30亿',bt(b,(b['zt_Tm2']==1)&(b['zt_Tm3']==1)&(b['是否涨停']==0)&(b['money']>3e9)&(b['M7']/b['M14']>1)&b['M14'].notna())))
# 再加一个：M7/M14>1.05 + 30亿
tests.append(('M7>1.05+30亿',bt(b,(b['zt_Tm2']==1)&(b['是否涨停']==0)&(b['money']>3e9)&(b['M7']/b['M14']>1.05)&b['M14'].notna())))
# 再加一个：连2板 + M7>1.05
tests.append(('连2板+M7>1.05',bt(b,(b['zt_Tm2']==1)&(b['zt_Tm3']==1)&(b['是否涨停']==0)&(b['money']>1.5e9)&(b['M7']/b['M14']>1.05)&b['M14'].notna())))

print('='*65)
print(f'{"测试项":<18} {"信号数":>6} {"胜率":>8} {"平均":>10}')
print('='*65)
for n,t in tests:
    if t:
        w=sum(1 for x in t if x>0)
        print(f'{n:<18} {len(t):>6} {w/len(t)*100:>7.1f}% {np.mean(t):>+9.2f}%')
    else:
        print(f'{n:<18} 无信号')
