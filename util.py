def make_status_response(version, protocol, maxplr, players, playerlist, motd, secure = False):
    return '''
{ 
    "version": { 
        "name": "''' + version + '''", "protocol": ''' + str(protocol) + ''' 
    }, "players": { 
        "max": ''' + str(maxplr) + ''', 
        "online": ''' + str(players) + ''', 
        "sample": ''' + playerlist + ''' 
    }, 
    "description": "''' + motd + '''", 
    "enforcesSecureChat": ''' + ("true" if secure else "false") + ''' 
}'''

