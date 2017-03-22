"""
Module to read data streams per line.

Supported inputs:
    - raw
    - json
    - json timeseries (contains "date" and "value" field)

Can produce the following generators:
    - raw lines
    - json objects
    - (date,value) tuples
Can produce the following output as non-generator:
    - pandas
"""
import json
from pandas import DataFrame
#To read data files
from datetime import datetime, timedelta
from dateutil import parser

class Reader(object):
    """
    Reader class to read data streams.
    """
    def __init__(self, inputStream, begin=None, end=None):
        """
        Create reader.

        Parameters
        ----------
        inputStream : file-like, anything that supports readlines or xreadlines.
            Input is read from this inputStream with readlines or xreadlines.
            If the end parameter is specified, the inputStream must be in
            chronological order.
        begin : datetime
            Inclusive begin date. All values before this date will be discarded.
        end : datetime
            Inclusive end date. All values after this date will be discarded.
        """
        self.fd_ = inputStream
        self.reset = False
        self.begin = begin
        self.end = end

    def setReset(self, reset=True):
        """
        Wether to start at the beginning of the stream before each read. Can be
        used to read the same data multiple times. Can only be used if the
        inputStream supports seek.
        """
        self.reset = reset

    def rawLines(self, n=None):
        """
        A generator that returns the first n lines.
        """
        if self.reset:
            self.fd_.seek(0)
        i = 0
        func = self.fd_.readlines
        if hasattr(self.fd_, 'xreadlines'):
            func = self.fd_.xreadlines

        for line in func():
            yield line
            i += 1
            if n is not None and i >= n:
                return

    def rawJSON(self, n=None):
        """
        A generator that returns the first n json objects.
        """
        if self.reset:
            self.fd_.seek(0)
        i = 0
        func = self.fd_.readlines
        if hasattr(self.fd_, 'xreadlines'):
            func = self.fd_.xreadlines
        for line in func():
            yield json.loads(line)
            i += 1
            if n is not None and i >= n:
                return

    def pandas(self, n=None, includeSensors=None, excludeSensors=None,
            includeBurst=True, onlyFirstValueOfBurst=False):
        """
            Import data into pandas DataFrame.

            Each row corresponds to a sensor value. Sensors are mapped to
            columns in the following way. If the sensor has a single value,
            then the column name is the sensor name.  If the sensor has a json
            value, the json keys in the root are mapped to column names:
            "<sensor>_<key>".  Burst sensor values are expanded into multiple
            rows, with the column names derived from the "headers" key in the
            root: "<sensor>_<header>".

            Parameters
            ----------
            includeSensors : iterable
                Only import data from these sensors.
            excludeSensors : iterable
                Don't import these sensors.
            includeBurst : boolean
                Whether to include burst sensors. (Default True).
            onlyFirstValueOfBurst : boolean
                Whether to only use a single value (the first) instead of the whole burst. (Default False).
        """
        if includeSensors is not None and excludeSensors is not None:
            raise (ValueError("Only one of includeSensors\
                    and excludeSensors can be set!"))
        elif onlyFirstValueOfBurst and not includeBurst:
            raise (ValueError("onlyFirstValueOfBurst can only be used withi\
					includeBurst=True"))
        dates = []
        data = []
        total = DataFrame([])
        bufSize = 10000
        def writeBack():
            """
            Store buffered data and dates into total.
            """
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

            date = datetime.fromtimestamp(row['date'])
            if self.begin is not None and date < self.begin:
                continue
            if self.end is not None and date > self.end:
                break

            value = row['value']

            if "burst-mode" in sensor and "values" in value and\
               "header" in value and "interval" in value:
                #append value for each row in burst
                sensorName = sensor.replace("(burst-mode)","").strip()
                names = []
                for key in value['header'].split(','):
                    keyName = key.strip().replace(' ', '_')
                    names.append("{}_{}".format(sensorName, keyName))
                if len(names) == 1:
                    #Rather just use sensor name
                    names = [sensorName]

                offset = date
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
                    if onlyFirstValueOfBurst:
                        break
            elif isinstance(value, dict):




                #prepend all keys with the sensor name and an underscore
                tmp = {}
                for (k,v) in value.items():
                    newKey = "{}_{}".format(sensor, k)
                    tmp[newKey] = v
                data.append(tmp)
                dates.append(date)
            else:
                data.append({sensor:row['value']})
                dates.append(date)

            if len(data) > bufSize:
                total = writeBack()
        total = writeBack()
        return total

    def dateValuePairs(self, n=None):
        """
        A generator that returns the first n (date, value) tuples.
        """
        for row in self.rawJSON(n):
            (date, value) = (parser.parse(row['date']), row['value'])
            #filter on date
            if self.begin is not None and date < self.begin:
                continue
            if self.end is not None and date > self.end:
                return

            yield (date, value)

    def dateJSONValuePairs(self, n=None):
        """
        A generator that returns the first n (date, jsonValue) tuples.
        """
        for (date, value) in self.dateValuePairs(n):
            yield (date, json.loads(value))
