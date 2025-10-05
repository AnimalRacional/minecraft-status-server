import io
def make_status_response(version, protocol, maxplr, players, playerlist, motd, secure = False, icon = ''):
    msg = '''
{ 
    "version": { 
        "name": "''' + version + '''", "protocol": ''' + str(protocol) + ''' 
    }, "players": { 
        "max": ''' + str(maxplr) + ''', 
        "online": ''' + str(players) + ''', 
        "sample": ''' + playerlist + ''' 
    }, 
    "description": "''' + motd + '''",'''
    if icon != '':
        msg += '''"favicon": "data:image/png;base64,''' + icon + '''",'''
    msg += '''"enforcesSecureChat": ''' + ("true" if secure else "false") + ''' 
}'''
    return msg
