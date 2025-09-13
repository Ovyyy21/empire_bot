class Config:
    # Server configuration
    URL = "wss://ep-live-mz-int1-sk1-gb1-game.goodgamestudios.com/"
    
    # Credentials
    USERNAME = "equilibrium fan"
    PASSWORD = "Apoc@123"
    
    # IDs
    MC_ID = '5499417'
    GREEN_ID = '0'
    
    # Map scanning parameters
    MAX_X = 1300
    MAX_Y = 1300
    STEP = 13
    
    # Message templates
    PING_MSG = "%xt%EmpireEx%pin%1%<RoundHouseKick>%"
    VER_CHK = "<msg t='sys'><body action='verChk' r='0'><ver v='166' /></body></msg>"
    LOGIN_MSG_TEMPLATE = (
        "<msg t='sys'><body action='login' r='0'>"
        "<login z='EmpireEx'><nick><![CDATA[{username}]]></nick>"
        "<pword><![CDATA[{password}]]></pword></login></body></msg>"
    )
    AUTO_JOIN = "<msg t='sys'><body action='autoJoin' r='-1'></body></msg>"
    ROUND_TRIP = "<msg t='sys'><body action='roundTrip' r='1'></body></msg>"
    LLI_MSG_TEMPLATE = (
        '%xt%EmpireEx%lli%1%{{'
        '"CONM":277,"RTM":73,"ID":0,"PL":1,"NOM":"{username}","PW":"{password}",'
        '"LT":null,"LANG":"en","DID":"0","AID":"1753205446671980389","KID":"",'
        '"REF":"https://empire.goodgamestudios.com","GCI":"","SID":9,"PLFID":1,"RCT":""}}%'
    )