from datetime import datetime, timedelta

A = datetime(2026, 3, 12, 15, 30, 0)
B = datetime(2026, 3, 12, 12, 15, 0)

delta = A - B
print(datetime(2026,1,1,0,0,0)+delta)

result = datetime.combine(A.date(), datetime.min.time()) + delta

print(result)
print(type(delta))