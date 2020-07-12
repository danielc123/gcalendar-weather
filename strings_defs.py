# -*- coding: utf-8 -*-
def gettext( text, lang='en' ):
    weekdays=('Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 
               'Saturday', 'Sunday', 'Today')
    if not (text in weekdays) and lang=='en':
        return text
    else:
        strings={
            'en':{
                'Monday':'MON', 'Tuesday':'TUE', 'Wednesday':'WED', 
                'Thursday':'THU', 'Friday':'FRI', 'Saturday':'SAT', 
                'Sunday':'SUN', 'Today':'TOD'        
            },
            'es':{
                'lunes':'LUN', 'martes':'MAR', 'mi\xe9rcoles':u'MIÉ', 
                'jueves':'JUE', 'viernes':'VIE', 's\xe1bado':u'SÁB', 
                'domingo':'DOM', 'Today':'HOY', 'TODAY':'HOY', 'TOMORROW':u'MAÑANA',
                'today':'hoy', 'tonight':'esta noche' ,'tomorrow':u'mañana',
                'Sunrise':'Amanecer', 'Sunset':'Atardecer','Daylight':'Horas de sol',
                'Sunset in':'Puesta de sol en', 'Sunrise in':'Salida del sol en',
                'on':'el'
            }
        }
        return strings[lang][text]
    




