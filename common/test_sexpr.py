

from sexpr import *

sexp = ''' ( ( data "quoted data" "123" "4.5" "4." ".5" "." "-123" "-4.5" "-4." "-.5" "+123" "+4.5" "+4." "+.5")
     (data "with \\"escaped quotes\\"" "with\nnewline" "with\rreturn")
     (numbers 123 1.2 4. .5 -123 -1.2 +123 +1.2 (123 (4.5) )
     (data "(more" "data)")))'''

print ('Input S-expression:')
print ('----------------------------------------')
print ('%r' % (sexp, ))
print ('----------------------------------------')

parsed = parse_sexp(sexp)
print ("\nParsed to Python:")
print ('----------------------------------------')
print (parsed)
print ('----------------------------------------')

print ("\nThen back to:")
print ('----------------------------------------')
print ("'%s'" % build_sexp(parsed))
print ('----------------------------------------')

print ("\nThen back to:")
print ('----------------------------------------')
print ("'%s'" % format_sexp(build_sexp(parsed)))
print ('----------------------------------------')
