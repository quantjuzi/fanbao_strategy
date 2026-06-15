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
def bt(ratio):
    c=(df['zt_Tm2']==1)&(df['是否涨停']==0)&(df['money']>1.5e9)&(df['M7']/df['M14']>ratio)&(df['实体涨跌幅']>-0.03)&df['M14'].notna()
    df['s']=c.astype(int);t=[]
    for _,r in df[df['s']==1].iterrows():
        cd=r['证券代码'];t1=r['index']
        td=df[(df['证券代码']==cd)&(df['index']>t1)]
        if td.empty:continue
        td2=df[(df['证券代码']==cd)&(df['index']>td.iloc[0]['index'])]
        if td2.empty:continue
        pnl=(td2.iloc[0]['close']-td.iloc[0]['open'])/td.iloc[0]['open']*100
        t.append(pnl)
    return t

print(f'{"M7/M14":<10} {"信号":>6} {"胜率":>7} {"平均":>8} {"平均赚":>8} {"平均亏":>8} {"盈亏比":>6} {"最大亏":>8}')
print('-'*65)
for r in [1.0,1.05,1.07,1.1]:
    t=bt(r);w=[x for x in t if x>0];l=[x for x in t if x<=0]
    print(f'{r:<10} {len(t):>6} {len(w)/len(t)*100:>6.1f}% {np.mean(t):>+7.2f}% {np.mean(w):>+7.2f}% {np.mean(l):>+7.2f}% {abs(np.mean(w)/np.mean(l)):>5.2f} {min(t):>+7.2f}%')
