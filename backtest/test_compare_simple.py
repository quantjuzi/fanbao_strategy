import sys,io
sys.stdout=io.TextIOWrapper(sys.stdout.buffer,encoding='utf-8')
import pandas as pd,numpy as np
CSV=r'C:\Users\Administrator\Desktop\全市场A股_2026-04-12_2026-06-12.csv'
df=pd.read_csv(CSV)
df['index']=pd.to_datetime(df['index'])
df.sort_values(['证券代码','index'],inplace=True)
df['M7']=df.groupby('证券代码')['close'].transform(lambda x:x.rolling(7).mean())
df['M14']=df.groupby('证券代码')['close'].transform(lambda x:x.rolling(14).mean())
df['zt_Tm2']=df.groupby('证券代码')['是否涨停'].shift(1)
df['实体涨跌幅']=(df['close']-df['open'])/df['open']

def bt(cond):
    df['sig']=cond.astype(int);t=[]
    for _,row in df[df['sig']==1].iterrows():
        c=row['证券代码'];t1=row['index']
        td=df[(df['证券代码']==c)&(df['index']>t1)]
        if td.empty:continue
        bp=td.iloc[0]['open']
        tp1=df[(df['证券代码']==c)&(df['index']>td.iloc[0]['index'])]
        if tp1.empty:continue
        t.append((tp1.iloc[0]['close']-bp)/bp*100)
    return t

b=(df['zt_Tm2']==1)&(df['是否涨停']==0)&(df['money']>1.5e9)&(df['M7']/df['M14']>1)&df['M14'].notna()
n=b&(df['实体涨跌幅']>-0.03)

t1=bt(b);t2=bt(n)
w1=[x for x in t1 if x>0];l1=[x for x in t1 if x<=0]
w2=[x for x in t2 if x>0];l2=[x for x in t2 if x<=0]

print('='*55)
print(f'{"":<14}{"基础版":>8}{"+实体>-3%":>12}')
print('='*55)
print(f'{"信号总笔数":<12}  {len(t1):>8}  {len(t2):>10}')
print(f'{"盈利笔数":<12}  {len(w1):>8}  {len(w2):>10}')
print(f'{"亏损笔数":<12}  {len(l1):>8}  {len(l2):>10}')
print(f'{"胜率":<12}  {len(w1)/len(t1)*100:>7.1f}%  {len(w2)/len(t2)*100:>9.1f}%')
print(f'{"平均盈亏":<12}  {np.mean(t1):>+7.2f}%  {np.mean(t2):>+9.2f}%')
print(f'{"平均盈利":<12}  {np.mean(w1):>+7.2f}%  {np.mean(w2):>+9.2f}%')
print(f'{"平均亏损":<12}  {np.mean(l1):>+7.2f}%  {np.mean(l2):>+9.2f}%')
print(f'{"盈亏比":<12}  {abs(np.mean(w1)/np.mean(l1)):>7.2f}  {abs(np.mean(w2)/np.mean(l2)):>9.2f}')
print(f'{"最大盈利":<12}  {max(t1):>+7.2f}%  {max(t2):>+9.2f}%')
print(f'{"最大亏损":<12}  {min(t1):>+7.2f}%  {min(t2):>+9.2f}%')
