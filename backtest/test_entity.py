
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
df['信号']=((df['zt_Tm2']==1)&(df['是否涨停']==0)&(df['money']>1.5e9)&(df['M7']/df['M14']>1)&(df['实体涨跌幅']>-0.03)&df['M14'].notna()).astype(int)
df['买入信号']=df.groupby('证券代码')['信号'].shift(1)
print(f'信号总数: {df["信号"].sum()}')
cash=50000;positions={};trades=[]
for cur in sorted(df['index'].unique()):
    today=df[df['index']==cur]
    if today.empty:continue
    for code in list(positions.keys()):
        row=today[today['证券代码']==code]
        if row.empty:continue
        bp=positions[code];sp=row.iloc[0]['close']
        pnl=(sp-bp)/bp*100;cash+=sp*100*0.99975;trades.append(pnl);del positions[code]
    for _,row in today[today['买入信号']==1].iterrows():
        if len(positions)>=3:break
        bp=row['open'];vol=int(cash/4/bp/100)*100
        if vol<100 or vol*bp*1.00025>cash:continue
        positions[row['证券代码']]=bp;cash-=vol*bp*1.00025
w=sum(1 for p in trades if p>0)
print(f'交易: {len(trades)}笔 胜率: {w}/{len(trades)} ({w/len(trades)*100:.1f}%) 平均: {np.mean(trades):+.2f}%')
