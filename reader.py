import json
from pandas import Series, DataFrame
#To read data files
import gzip
from datetime import datetime, date, time, timedelta
from dateutil import parser

class Reader:
    def __init__(self, fd, begin=None, end=None):
        self.fd = fd
        self.reset = True
        self.begin=begin
        self.end=end

    def setReset(self, reset=True):
        self.reset = reset
    
    def rawLines(self, n=None):
        if self.reset:
            self.fd.seek(0)
        i=0
        func = self.fd.readlines
        if hasattr(self.fd, 'xreadlines'):
                func = self.fd.readlines

        for line in func():
            yield line
            i += 1
            if n is not None and i >= n: return

    def rawJSON(self, n=None):
        if self.reset:
            self.fd.seek(0)
        i=0
        func = self.fd.readlines
        if hasattr(self.fd, 'xreadlines'):
                func = self.fd.readlines
        for line in func():
            yield json.loads(line)
            i += 1
            if n is not None and i >= n: return

    def pandas(self, n=None, filterSensors=None):
        """
            Create pandas.
            TODO: optimise memory usage as it uses A LOT
        """
        dates = {}
        data = {}
        for row in self.rawJSON(n):
            sensor = row["sensor_name"]
	    if filterSensors != None and sensor not in filterSensors:
                continue
            if not sensor in data:
                data[sensor] = []
                dates[sensor] = []
            value = row['value']
            if isinstance(value, dict):
                #prepend all keys with the sensor name and an underscore
                for key in value.keys():
                    newKey = "{}_{}".format(sensor, key)
                    value[newKey] = value.pop(key)
            data[sensor].append(row['value'])
            dates[sensor].append(datetime.fromtimestamp(row['date']))
        #Note, we cannot create a data frame at once since lengths don't match
        dataframes = []
        for sensor in data.keys():
            columns = None
            if isinstance(data[sensor][0], dict):
                columns = None
            else:
                columns = [sensor]
            df = DataFrame(data[sensor], index=dates[sensor], columns=columns)
            dataframes.append(df)

        if len(dataframes) == 0:
            return DataFrame()
        total = dataframes[0]
        for df in dataframes[1:]:
            total = total.join(df)
        return total

    def dateValuePairs(self, n=None):
        for x in self.rawJSON(n):
            (date,value) = (parser.parse(x['date']), x['value'])
            #filter on date
            if self.begin is not None and date < self.begin:
                    continue
            if self.end is not None and date > self.end:
                    return

            yield (date,value)

    def dateJSONValuePairs(self, n=None):
        for (date, value) in self.dateValuePairs(n):
            yield (date, json.loads(value))
