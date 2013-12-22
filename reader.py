import json
from pandas import Series, DataFrame
#To read data files
import gzip
from datetime import datetime, date, time, timedelta
from dateutil import parser

from pympler.asizeof import asizeof

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

    def pandas(self, n=None, includeSensors=None, excludeSensors=None, includeBurst=True):
        """
            Import data into pandas.

            Parameters
            ----------
            includeSensors : iterable
                Only import data from these sensors.
            excludeSensors : iterable
                Don't import these sensors.
            includeBurst : boolean
                Whether to include burst sensors. (Default True).
        """
        if includeSensors is not None and excludeSensors is not None:
                raise (ValueException("Only one of includeSensors and excludeSensors can be set!"))
        dates = []
        data = []
        total = DataFrame([])
        bufSize = 10000
        def writeBack():
            #put buffer into DataFrame
            df = DataFrame(data, index=dates)
            #clear the buffer
            del data[:]
            del dates[:]
            #append to total
            return total.append(df)
            #return total.join(df)

        for row in self.rawJSON(n):
            sensor = row["sensor_name"]
            if excludeSensors != None and sensor in excludeSensors:
                continue
            if includeSensors != None and sensor not in includeSensors:
                continue
            if not includeBurst and "(burst-mode)" in sensor:
                continue
            value = row['value']

            if "burst-mode" in sensor and "values" in value and "header" in value and "interval" in value:
                #append value for each row in burst
                sensorName = sensor.replace("(burst-mode)","").strip()
                names = ["{}_{}".format(sensorName,x.strip()).replace(' ','_') for x in value['header'].split(',')]
                offset = datetime.fromtimestamp(row['date'])
                interval = timedelta(milliseconds=value['interval'])
                cumTime = offset
                for v in value['values']:
                    if len(names) == 1:
                        singleValue = {names[0]:v}
                    else:
                        singleValue = dict(zip(names, v))
                    data.append(singleValue)
                    dates.append(cumTime)
                    cumTime += interval
            elif isinstance(value, dict):
                #prepend all keys with the sensor name and an underscore
                for key in value.keys():
                    newKey = "{}_{}".format(sensor, key)
                    value[newKey] = value.pop(key)
                data.append(row['value'])
                dates.append(datetime.fromtimestamp(row['date']))
            else:
                data.append({sensor:row['value']})
                dates.append(datetime.fromtimestamp(row['date']))

            if len(data) > bufSize:
                total = writeBack()
        total = writeBack()
        print round(asizeof(total)/1024.0)
        return total

    def pandas_old(self, n=None, filterSensors=None):
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
