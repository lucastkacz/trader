import pandas as pd
import numpy as np
import plotly.express as px
import scipy.stats as stats
import plotly.graph_objects as go

# Dummy data
np.random.seed(42)
hist_data = pd.Series(np.random.normal(0, 1, 1000), name="AssetA")

fig = px.histogram(
    hist_data,
    x="AssetA",
    nbins=50,
    marginal="box",
    histnorm="probability density",
    color_discrete_sequence=['#00bfff']
)

kde = stats.gaussian_kde(hist_data)
x_kde = np.linspace(hist_data.min(), hist_data.max(), 500)
y_kde = kde(x_kde)

# Find the row/col of the histogram trace
hist_trace = next(t for t in fig.data if t.type == 'histogram')
yaxis = hist_trace.yaxis
if yaxis == 'y':
    row, col = 1, 1
elif yaxis == 'y2': # Not exactly but we can just use the axis names
    row, col = 2, 1
else:
    row, col = 1, 1

# Actually, Plotly allows adding trace specifying the axis directly
fig.add_trace(go.Scatter(
    x=x_kde,
    y=y_kde,
    mode='lines',
    line=dict(color='#ff7f0e', width=2),
    name='KDE',
    xaxis=hist_trace.xaxis,
    yaxis=hist_trace.yaxis
))

fig.write_html("test_kde.html")
print("Success")
