
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
    trades=[]
    for _,row in df[df['sig']==1].iterrows():
        c=row['证券代码'];t1=row['index']
        td=df[(df['证券代码']==c)&(df['index']>t1)]
        if td.empty:continue
        bp=td.iloc[0]['open']
        tp1=df[(df['证券代码']==c)&(df['index']>td.iloc[0]['index'])]
        if tp1.empty:continue
        sp=tp1.iloc[0]['close']
        trades.append({'code':c,'信号日':str(t1.date()),'买入日':str(td.iloc[0]['index'].date()),'卖出日':str(tp1.iloc[0]['index'].date()),'买入价':bp,'卖出价':sp,'盈亏':(sp-bp)/bp*100})
    return trades

base=(df['zt_Tm2']==1)&(df['是否涨停']==0)&(df['money']>1.5e9)&(df['M7']/df['M14']>1)&df['M14'].notna()
t3=(df['zt_Tm2']==1)&(df['zt_Tm3']==1)&(df['是否涨停']==0)&(df['money']>1.5e9)&(df['M7']/df['M14']>1)&df['M14'].notna()

for name,cond in [('基础(15亿)',base),('+T-3涨停',t3)]:
    t=bt(cond)
    if not t:print(f'{name}: 无信号');continue
    p=[x['盈亏'] for x in t]
    w=[x for x in p if x>0];l=[x for x in p if x<=0]
    print(f'=== {name} ===')
    print(f'信号总数:   {len(t)}')
    print(f'有信号天数:  {len(set(x["信号日"] for x in t))}')
    print(f'日均信号数:  {len(t)/len(set(x["信号日"] for x in t)):.1f}')
    print(f'胜率:       {len(w)}/{len(p)} ({len(w)/len(p)*100:.1f}%)')
    print(f'平均盈亏:    {np.mean(p):+.2f}%')
    print(f'平均盈利:    {np.mean(w):+.2f}%' if w else 'N/A')
    print(f'平均亏损:    {np.mean(l):+.2f}%' if l else 'N/A')
    print(f'盈亏比:      {abs(np.mean(w)/np.mean(l)):.2f}' if w and l else 'N/A')
    print(f'最大盈利:    {max(p):+.2f}%')
    print(f'最大亏损:    {min(p):+.2f}%')
    print(f'收益标准差:  {np.std(p):.2f}%')
    print()
