def convertHMS(value):
    sec = int(value)  # convert value to number if it's a string
    days = sec // (24 * 3600)  # get days
    sec = sec % (24 * 3600)  # get remaining seconds
    hours = sec // 3600  # get hours
    sec %= 3600  # get remaining seconds
    minutes = sec // 60  # get minutes
    seconds = sec % 60  # get remaining seconds
    if days > 0:
        days = str(days) + 'd '
    else:
        days = ''
    if hours > 0:
        hours = str(hours) + 'hr '
    else:
        hours = ''
    if minutes > 0:
        minutes = str(minutes) + 'm '
    else:
        minutes = ''
    if seconds > 0:
        seconds = str(seconds) + 's'
    else:
        if hours == '' and minutes == '':
            seconds = str(seconds) + 's'
        else:
            seconds = ''
    if (days + hours + minutes + seconds).endswith(' '):
        return (days + hours + minutes + seconds)[:-1]
    return days + hours + minutes + seconds