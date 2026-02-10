import datetime as dt

def get_timestamp()-> float:
    timestamp = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    date, timestamp = timestamp.split()
    return timestamp 

def get_date()-> str:
    date = dt.datetime.now().strftime("%Y-%m-%d")
    return date

   

x = get_timestamp()
print(x)
print(get_date())





'''The issue of this timestamp system is to find the duration and the corresponding time, the current state does not reflect my intention
this must be altered in the future bla bla bla ill get to it when i have time'''