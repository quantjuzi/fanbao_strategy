# fanbao backtest
import sys,io
sys.stdout=io.TextIOWrapper(sys.stdout.buffer,encoding='utf-8')
import pandas as pd,numpy as np

CSV=r'C:\Users\Administrator\Desktop\全市场A股_2026-04-12_2026-06-12.csv'
df=pd.read_csv(CSV)
df['index']=pd.to_datetime(df['index'])
df.sort_values(['证券代码','index'],inplace=True)

df['昨收']=df.groupby('证券代码')['close'].shift(1)
df['昨高']=df.groupby('证券代码')['high'].shift(1)
df['昨涨跌']=df.groupby('证券代码')['close'].pct_change().shift(1)
df['今涨跌']=df.groupby('证券代码')['close'].pct_change()
df.dropna(inplace=True)

# 信号在今天收盘确定，明天开盘买入 → 信号往后移1天
df['信号']=((df['close']>df['open'])&(df['close']>df['昨高'])&(df['昨涨跌']<0)&(df['money']>=10e9)&(df['今涨跌']>=0.03)&(df['是否涨停']!=1)).astype(int)
df['买入信号']=df.groupby('证券代码')['信号'].shift(1)

total=int(df['信号'].sum())
print(f'反包信号总数: {total}')
print()

# 回测
cash=50000
deals=[]
positions={}

for cur in sorted(df['index'].unique()):
    today=df[df['index']==cur]
    if today.empty:continue
    
    # 卖出（今天开盘卖持有的票）
    for c in list(positions.keys()):
        r=today[today['证券代码']==c]
        if r.empty:continue
        bp,vol=positions[c]
        sp=r.iloc[0]['open']
        pnl=(sp-bp)/bp*100
        cash+=sp*vol*0.99975
        deals.append((cur,c,bp,sp,pnl))
        del positions[c]
    
    # 买入信号（昨天出了信号，今天开盘买）
    for _,r in today[today['买入信号']==1].iterrows():
        if len(positions)>=2:break
        bp=r['open']
        vol=int(cash/3/bp/100)*100
        if vol<100:continue
        if vol*bp*1.00025>cash:continue
        positions[r['证券代码']]=(bp,vol)
        cash-=vol*bp*1.00025

pnls=[d[4] for d in deals]
w=sum(1 for p in pnls if p>0)
print(f'交易: {len(deals)}笔  胜率: {w}/{len(deals)} ({w/len(deals)*100:.1f}%)  平均: {np.mean(pnls):+.2f}%  最大盈利: {max(pnls):+.2f}%  最大亏损: {min(pnls):+.2f}%')
print()
if deals:
    for d,c,bp,sp,p in deals:
        print(f'  {str(d.date())[5:]} {c} 买{bp:.2f} 卖{sp:.2f} {p:+.2f}%')