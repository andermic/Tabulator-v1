#!/usr/bin/env python

"""
Developed with Python 2.6.2
Name: tabulator.py
Author: Mike Anderson
Created: Aug 5, 2009
Purpose: To define a class that takes as input a merged BallotInfo
 file and generates a report
"""

from __future__ import with_statement
import yaml
import sys
from datetime import date

from xml_serializer import xml_serialize
import audit_header

class Tabulator(object):
    def __init__(self, args):
        self.precs = 0
        # Load ballot records from yaml file
        self.input = args[0]
        try:
            stream = open(''.join([self.input,'.yml']), 'r')
        except IOError:
            print(''.join(['Unable to open ',self.input,'\n']))
            raise
        else:
            a = audit_header.AuditHeader()
            a.load_from_file(stream)
            self.b = list(yaml.load_all(stream))

        # Load the jurisdiction slate or precinct contestlist template
        try:
            stream = open(''.join([args[1],'.yml']), 'r')
        except IOError:
            print(''.join(['Unable to open ',self.input,'\n']))
            raise
        else:
            a = audit_header.AuditHeader()
            a.load_from_file(stream)
            self.template_type = a.type
            self.templ = yaml.load(stream)

        # Add the vote counts of candidates with the same ID# using
        #  sumation(). Write the vote totals for each candidate to the
        #  report stream.
        d = date.today()
        self.header = '\n'.join(['Election Summary Report,,',
         'Generated by TrustTheVote Tabulation and Reporting Module,,',
         'Report generated on, %d-%d-%d,\n' % (d.month, d.day, d.year)])

        b = self.sumation()
        self.serialize_csv_pvt_html(b)

        # Dump output into a file in yaml format
        with open(''.join([self.input,'_report.yml']), 'w') as stream:
            yaml.dump(b, stream)

        # Dump output into a file in XML file
        with open(''.join([self.input,'_report.xml']), 'w') as stream:
            stream.writelines(xml_serialize(b, 0))

    def sumation(self):
        """
        Sum up the separate vote counts in each record for each
         candidate and return the cumulative result as a dictionary.
        """

        sum_list = {}

        # If the template is a precinct_contestlist, then populate its
        #  precinct_list with only the one precinct
        if self.template_type == 'precinct_contestlist':
            self.templ['precinct_list']=[{'display_name':self.templ['prec_ident']}]

        # Iterate through all ballot_counter records given as input
        for rec in self.b:
            # Find the precinct associated with the current record
            for precinct in self.templ['precinct_list']:
                if precinct['ident'] == rec['prec_ident']:
                    prec = precinct['display_name']
            type = rec['vote_type']
            # Make a set of keys for the given precinct if they don't
            #  yet exist.
            if not sum_list.has_key(prec):
                sum_list[prec] = {}
                sum_list[prec]['Polling'] = {}
                sum_list[prec]['Absentee'] = {}
                sum_list[prec]['Early Voting'] = {}
                sum_list[prec]['Other'] = {}
                sum_list[prec]['Totals'] = {}
            # Iterate through all of the contests in the given record
            for i in range(len(rec['contest_list'])):
                cont = rec['contest_list'][i]
                co_name = cont['ident']
                # Make a set of keys for the given contest if they don't
                #  yet exist for the current prec and type
                if not sum_list[prec][type].has_key(co_name):
                    sum_list[prec][type][co_name] = {}
                    sum_list[prec][type][co_name]['*TOTAL'] = 0
                    sum_list[prec][type][co_name]['*BLANK'] = 0
                    sum_list[prec][type][co_name]['*OVER'] = 0
                if not sum_list[prec]['Totals'].has_key(co_name):
                    sum_list[prec]['Totals'][co_name] = {}
                    sum_list[prec]['Totals'][co_name]['*TOTAL'] = 0
                    sum_list[prec]['Totals'][co_name]['*BLANK'] = 0
                    sum_list[prec]['Totals'][co_name]['*OVER'] = 0
                # Keep a running total for Total, Blank, and Over fields
                #  for this contest
                sum_list[prec][type][co_name]['*TOTAL'] += \
                 cont['total_votes']
                sum_list[prec][type][co_name]['*BLANK'] += \
                 cont['uncounted_ballots']['blank_votes']
                sum_list[prec][type][co_name]['*OVER'] += \
                 cont['uncounted_ballots']['over_votes']
                sum_list[prec]['Totals'][co_name]['*TOTAL'] += \
                 cont['total_votes']
                sum_list[prec]['Totals'][co_name]['*BLANK'] += \
                 cont['uncounted_ballots']['blank_votes']
                sum_list[prec]['Totals'][co_name]['*OVER'] += \
                 cont['uncounted_ballots']['over_votes']
                # Iterate through the candidates in the given contest
                for j in range(len(cont['candidates'])):
                    cand = cont['candidates'][j]
                    ca_name = cand['display_name']
                    # Make new keys in sum_list for each candidate if
                    #  they don't yet exist
                    if not sum_list[prec][type][co_name].has_key(ca_name):
                        sum_list[prec][type][co_name][ca_name] = 0
                    if not sum_list[prec]['Totals'][co_name].has_key(ca_name):
                        sum_list[prec]['Totals'][co_name][ca_name] = 0
                    sum_list[prec][type][co_name][ca_name] += cand['count']
                    sum_list[prec]['Totals'][co_name][ca_name] += cand['count']
        return sum_list

    def serialize_csv_pvt_html(self, sum_list):
        """
        Serialize a list of contests and their respective candidate
         vote counts into a .csv, .pvt, & .html format, and output each
         to a file.
        """

        stream = open(''.join([self.input, '_report.csv']), 'w')
        stream.write(self.header)
        if self.input.rfind('/') != -1:
            fname = self.input[self.input.rfind('/') + 1:]
        else:
            fname = self.input
        stream.write('Input BallotInfo File, %s.yml,\n' % fname)
        stream.write(',,\n')

        s_pvt = open(''.join([self.input,'_report_pvt.csv']), 'w')
        s_pvt.write(self.header)
        s_pvt.write('Contest,Precinct,Type,Name,Party,Count,\n')

        s_html = open(''.join([self.input,'_report.html']), 'w')

        # Output voter turnout information first
        stream.write(',,Turnout,\n')
        stream.write(',,Reg. Voters,Cards Cast,%Turnout,\n')
        s_html.write('\n'.join(['<table>',
         '<tr><td class="contest">TURNOUT</td></tr>', '<tr class="header">',
         '<td></td>', '<td><span>Reg. Voters</span></td>',
         '<td><span>Cards Cast&nbsp;</span></td>',
         '<td><span>% Turnout&nbsp;&nbsp;</span></td>', '</tr>',
         '<tr><td>Jurisdiction Wide</td></tr>\n']))
        for prec in self.templ['precinct_list']:
            stream.write(','.join([str(prec['display_name']), '\n']))
            s_html.write(''.join(['<tr><td>&nbsp;&nbsp;',
             str(prec['display_name']), '</td></tr>\n']))
            for type in ['Polling','Absentee','Early Voting','Other','Totals']:
                num_voters = prec['registered_voters']
                cards_cast = 200  # A hardcoded dummy value
                turnout = (float(cards_cast))/num_voters * 100
                d_name = prec['display_name']

                stream.write(',%s,%d,%d,%.2f,\n' % 
                 (type, num_voters, cards_cast, turnout) )
                s_pvt.write('*TURNOUT,%d,%s,Reg. Voters,,%d,\n' %
                 (d_name, type, num_voters) )
                s_pvt.write('*TURNOUT,%d,%s,Cards Cast,,%d,\n' %
                 (d_name, type, cards_cast) )
                s_pvt.write('*TURNOUT,%d,%s,%% Turnout,,%.2f,\n' %
                 (d_name, type, turnout) )
                s_html.write('\n'.join(['<tr>',
                 '<td>&nbsp;&nbsp;&nbsp;&nbsp;%s</td>' % type,
                 '<td>%d</td>' % num_voters, '<td>%d</td>' % cards_cast,
                 '<td>%.2f</td>' % turnout, '</tr>\n']) )
        s_html.write('</table>\n\n\n')

        # Make a list of "candidates" that will be included in every
        #  contest by default
        TBO_list = [{'display_name':'*TOTAL','party_ident':''},
                    {'display_name':'*BLANK','party_ident':''},
                    {'display_name':'*OVER','party_ident':''}]

        for cont in self.templ['contest_list']:
            co_name = cont['ident']
            stream.write('\n,,%s,\n' % cont['display_name'].upper())
            stream.write(',,Reg. Voters,Times Counted,Total Votes,')
            stream.write('Times Blank Voted,Times Over Voted,')
            s_html.write('<table>\n')
            s_html.write('<tr><td class="contest">%s</td></tr>\n' % co_name.upper())
            s_html.write( '\n'.join(['<tr class="header">', '<td></td>',
             '<td><span>Reg. Voters</span></td>', '<td><span>Times Counted</span></td>',
             '<td><span>Total Votes</span></td>', '<td><span>Blank Votes</span></td>',
             '<td><span>Over Votes&nbsp;</span></td>\n']) )
            for cand in cont['candidates']:
                stream.write(cand['display_name'])
                s_html.write('<td><span>%s</span></td>\n' % cand['display_name'])
                if cand['display_name'] != 'Write-In Votes':
                    stream.write(',')
            stream.write('\n')
            s_html.write('</tr>\n<tr><td>Jurisdiction Wide</td></tr>\n')

            for prec in self.templ['precinct_list']:
                pr_name = prec['display_name']
                # If no voting data is available for the given precinct
                #  and contest combination, then go on to the next
                #  precinct.
                if not sum_list.has_key(pr_name) or \
                 (not sum_list[pr_name]['Polling'].has_key(co_name) and \
                 not sum_list[pr_name]['Absentee'].has_key(co_name) and \
                 not sum_list[pr_name]['Early Voting'].has_key(co_name) and \
                 not sum_list[pr_name]['Other'].has_key(co_name) and \
                 not sum_list[pr_name]['Totals'].has_key(co_name)):
                     continue

                stream.write('%d,\n' % pr_name)
                s_html.write('<tr><td>&nbsp;&nbsp;%d</td></tr>\n' % pr_name)
                for type in ['Polling','Absentee','Early Voting','Other','Totals']:
                    if sum_list[pr_name][type].has_key(co_name):
                        temp = sum_list[pr_name][type][co_name]
                    else:
                        stream.write(',%s,\n' % type)
                        s_html.write(''.join(['<tr><td>&nbsp;&nbsp;&nbsp;&nbsp;',
                         '%s</td></tr>\n' % type]))
                        continue
                    num_voters = (prec['registered_voters'])
                    cards_cast = temp['*TOTAL'] + temp['*BLANK'] + temp['*OVER']
                    stream.write(',%s,%d,%d,' % (type, num_voters, cards_cast))
                    s_html.write(''.join(['<tr>\n<td>&nbsp;&nbsp;&nbsp;&nbsp;',
                     '%s</td>\n<td>%d</td>\n<td>%d</td>\n' %
                     (type, num_voters, cards_cast) ]) )
                    for cand in TBO_list + cont['candidates']:
                        ca_name = cand['display_name']
                        stream.write('%s,' % temp[ca_name])
                        if type != 'Totals' and ca_name != '*TOTAL':
                            s_pvt.write('%s,%d,%s,%s,%s,%d,\n' % (co_name,
                             pr_name, type, ca_name, cand['party_ident'],
                             temp[ca_name]) )
                        s_html.write('<td>%d</td>\n' % temp[ca_name])
                    stream.write('\n')
                    s_html.write('</tr>\n')
            s_html.write('</table>\n\n')
        stream.close()
        s_pvt.close()
        s_html.close()

def main():
    # Output a usage message if incorrect number of command line args
    if( len(sys.argv) != 3 ):
        print "Usage: [MERGED INPUT FILE] [ELECTION TEMPLATE FILE]"
        exit()

    t = Tabulator(sys.argv[1:])

    print 'SOVC report created in %s_report.csv, %s_report_pvt.csv,\n' % \
     (sys.argv[1], sys.argv[1])
    print '%s_report.yml, and %s_report.xml\n' % (sys.argv[1], sys.argv[1])

    return 0

if __name__ == '__main__': main()
