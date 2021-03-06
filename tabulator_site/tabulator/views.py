from __future__ import with_statement

import os
import json
from copy import deepcopy

from django.template import Context, loader, RequestContext
from django.http import HttpResponse, HttpResponseRedirect, HttpRequest
from django.shortcuts import render_to_response
from django.conf import settings
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django import forms

import test_data_generator as TDG
import merger
import audit_header
import tabulator


class FileForm(forms.Form):
    file = forms.Field(widget=forms.FileInput, required=False)

def welcome_handler(request):
    """
    Handle requests/responses to and from the welcome template
    """

    # Check to see if the client is posting data
    if request.method == 'POST':        
        # Check to see if the client is attempting to log in
        if request.POST.has_key('username'):
            logout(request)
            u_attempt = request.POST['username']
            p_attempt = request.POST['password']
            user = authenticate(username=u_attempt, password=p_attempt)
            if user is not None:
                if user.is_active:
                    login(request, user)
            login_status = request.user.is_authenticated()
            return HttpResponse(login_status)            
        # Check to see if the client wants to log the user out
        elif request.POST.has_key('logout_user'):
            logout(request)
    c = get_file_data()
    return render_to_response('welcome.html', c,
     context_instance=RequestContext(request, processors=[settings_processor]))

@login_required
def tdg_handler(request):
    """
    Handle requests/responses to and from the test data generator template
    """
    
    # Check to see if the client is posting data
    if request.method == 'POST':
        # Check to see if the client wants to generate a file
        if request.POST.has_key('arguments_tdg'):
            #Get the arguments from the user's request
            args = request.POST.getlist('arguments_tdg')[0]
            args = args.split(' ')[1:]
            
            # Make arguments consistent with where data is stored on the
            #  server, using DATA_PATH from settings.py
            if args[0] == 'jurisdiction' or args[0] == 'contestlist':
                args[1] = ''.join([settings.DATA_PATH, 'templates/', args[1]])
            elif args[0] == 'counts':
                args[2] = ''.join([settings.DATA_PATH, 'templates/', args[2]])
                args[3] = ''.join([settings.DATA_PATH,'bal_count_tot/',args[3]])
            P = TDG.ProvideRandomBallots(args)  # Make a file
        # Check to see if client wants to rename a file
        elif request.POST.has_key('old_name'):
            rename_file(request.POST)
            return HttpResponse()
    c = get_file_data()
    c['upload_form'] = FileForm()
    return render_to_response('tdg.html', c,
    context_instance=RequestContext(request, processors=[settings_processor]))

@login_required
def merge_handler(request):
    """
    Handle requests/responses to and from the merger template
    """

    # Check to see if the client is posting data
    if request.method == 'POST':
        # Check to see if client wants to merge files
        if request.POST.has_key('arguments'):
            #Get the arguments from the user's request
            args = request.POST.getlist('arguments')[0]
            args = args.split(' ')[1:]
            
            # Arguments will be made consistent with where data is
            #  stored on the server, as given by DATA_PATH
            args[0] = ''.join([settings.DATA_PATH, 'templates/', args[0]])

            if os.listdir(''.join([settings.DATA_PATH,'bal_count_tot/'])).\
             count(''.join([args[1],'.yml'])) == 1:
                args[1] = ''.join([settings.DATA_PATH, 'bal_count_tot/', args[1]])
            else:
                args[1] = ''.join([settings.DATA_PATH, 'tab_aggr/', args[1]])
            if os.listdir(''.join([settings.DATA_PATH, 'bal_count_tot/'])).\
             count(''.join([args[2], '.yml'])) == 1:
                args[2] = ''.join([settings.DATA_PATH, 'bal_count_tot/', args[2]])
            else:
                args[2] = ''.join([settings.DATA_PATH, 'tab_aggr/', args[2]])
            fname = args[3]
            args[3] = ''.join([settings.DATA_PATH, 'tab_aggr/', args[3]])

            m = merger.Merger(*args)
            if m.validate() == True:
                m.merge(args[3])
        # Check to see if client wants to rename a file
        elif request.POST.has_key('old_name'):
            rename_file(request.POST)
            return HttpResponse()
    c = get_file_data()
    return render_to_response('merge.html', c,
     context_instance=RequestContext(request, processors=[settings_processor]))

@login_required
def tab_handler(request):
    """
    Handle requests/responses to and from the tabulator template
    """

    # Check to see if the client is posting data
    if request.method == 'POST':
        # Check to see if client wants to merge files
        if request.POST.has_key('arguments'):
            #Get the arguments from the user's request
            args = request.POST.getlist('arguments')[0]
            args = args.split(' ')[1:]

            args[0] = ''.join([settings.DATA_PATH, 'tab_aggr/', args[0]])
            args[1] = ''.join([settings.DATA_PATH, 'templates/', args[1]])

            t = tabulator.Tabulator(args)
            # Move the newly generated reports into the reports/ folder
            os.system('mv %s_report* %sreports/' % (args[0], settings.DATA_PATH))
    c = get_file_data()
    return render_to_response('tabulator.html', c,
     context_instance=RequestContext(request, processors=[settings_processor]))

@login_required
def tdg_file_handler(request, fname):
    """
    Read the contents of a requested tdg file from memory, mark it up so
     that it displays correctly as html, and render it.
    """

    if os.listdir(''.join([settings.DATA_PATH, 'templates/'])).count(fname) == 1:
        fpath = '%stemplates/%s' % (settings.DATA_PATH,fname)
    else:
        fpath = '%sbal_count_tot/%s' % (settings.DATA_PATH,fname)

    with open(fpath, 'r') as stream:
        lines = stream.readlines()    
    c = Context({'lines':mark_up(lines)})
    return render_to_response('tdg_file.html', c,
     context_instance=RequestContext(request, processors=[settings_processor]))

@login_required
def merge_file_handler(request, fname):
    """
    Read the contents of a requested merge file from memory, mark it up
     so that it displays correctly as html, and render it.
    """

    c = Context()
    
    # Read in file data stored on server. A merged file may not have
    #  have been created, but try to load it and format it.
    try:
        stream = open('%stab_aggr/%s' % (settings.DATA_PATH, fname), 'r')
    except IOError:
        pass
    else:
        c['merged'] = mark_up(stream.readlines())

    fname = fname[:fname.rfind('.')]
    with open('%stab_aggr/%s.log' % (settings.DATA_PATH, fname), 'r') as stream:
        c['log'] = mark_up(stream.readlines())

    return render_to_response('merge_file.html', c,
     context_instance=RequestContext(request, processors=[settings_processor]))

@login_required
def tab_file_handler(request, fname):
    """
    Read the contents of a requested tabulator file from memory, mark it
     up so that it displays correctly as html, and render it.
    """

    with open('%sreports/%s' % (settings.DATA_PATH, fname), 'r') as stream:
        lines = stream.readlines()
    formatted_lines = []
    
    # If requested file is a .yml or .xml, fully markup. If .csv, then
    #  only do a little bit of formatting. If .html, then do even less.
    if fname.rfind('.yml') != -1 or fname.rfind('.xml') != -1:
        formatted_lines = mark_up(lines)
    elif fname.rfind('.csv') != -1:
        for line in lines:
            line = line.replace('\n', '<br/>')
            formatted_lines.append(line.replace(' ', '&nbsp;'))
    else:
        formatted_lines = lines
    c = Context({'lines':formatted_lines})
    return render_to_response('tab_file.html', c,
     context_instance=RequestContext(request, processors=[settings_processor]))

@login_required
def download_handler(request, file_and_parent):
    """
    Handle a request to download a file
    """

    fp = file_and_parent
    parent = fp[:fp.rfind('/')]
    fname = fp[fp.find('/') + 1:]
    if parent == 'templates' and \
     fname not in os.listdir(''.join([settings.DATA_PATH, parent])):
        fp = '%s/%s' % ('bal_count_tot', fname)
        
    # Return a response consistent with the type of file to download
    path = ''.join([settings.DATA_PATH, fp])
    if fname.rfind('.csv') != -1:
        response = HttpResponse(open(path, 'r'), mimetype="text/csv")
    elif fname.rfind('.xml') != -1:
        response = HttpResponse(open(path, 'r'), mimetype="text/xml")
    elif fname.rfind('.html') != -1:
        response = HttpResponse(open(path, 'r'), mimetype="text/html")
    else:
        response = HttpResponse(open(path, 'r'), mimetype="text/plain")
    response['Content-Disposition'] = ''.join(['attachment; filename=', fname])
    return response

@login_required
def upload_handler(request):
    """
    Handle a request to upload a file
    """

    if request.method == 'POST':
        post_copy = request.POST.copy()
        post_copy.update(request.FILES)
        
        # Check to see if a file was uploaded
        if 'uploaded_file' in post_copy:
            file_ = post_copy['uploaded_file']
            n = file_.name

            # Uploaded file should have a .yml file extension
            if len(n) >= len('.yml') and n[len(n) - len('.yml'):] == '.yml':

                # Uploaded file should be no bigger than a megabyte
                meg = 1024*1024
                if file_.size <= meg:
                    with open(''.join([settings.DATA_PATH, \
                     'templates/', n]), 'wb') as fd:
                        fd.write(file_.read())

    return HttpResponseRedirect('/tdg')
    
@login_required
def logout_handler(request):
    """
    Handle a logout request
    """
    
    logout(request)
    return HttpResponseRedirect('/welcome')
    
@login_required
def delete_file_handler(request):
    """
    Find and delete a list of files that were generated by this system
    """
    
    for file in request.POST.getlist('delete'):
        if os.listdir( ''.join([settings.DATA_PATH, 'reports/']) ). \
         count( ''.join([file, '_report.csv']) ) == 1:
            os.system('rm -f %sreports/%s_report*' % (settings.DATA_PATH, file))
        if os.listdir( ''.join([settings.DATA_PATH, 'templates/']) ). \
         count( ''.join([file, '.yml']) ) == 1:
            os.system('rm -f %stemplates/%s.*' % (settings.DATA_PATH, file))
        if os.listdir( ''.join([settings.DATA_PATH, 'bal_count_tot/']) ). \
         count( ''.join([file, '.yml']) ) == 1:
            os.system('rm -f %sbal_count_tot/%s.*' % (settings.DATA_PATH, file))
        if os.listdir( ''.join([settings.DATA_PATH, 'tab_aggr/']) ). \
         count( ''.join([file, '.yml']) ) == 1:
            os.system('rm -f %stab_aggr/%s.*' % (settings.DATA_PATH, file))
        if os.listdir( ''.join([settings.DATA_PATH, 'tab_aggr/']) ). \
         count( ''.join([file, '.log']) ) == 1:
            os.system('rm -f %stab_aggr/%s.log' % (settings.DATA_PATH, file))
    return HttpResponse()

def rename_file_handler(request):
    """
    Find and rename a file that was generated by this system
    """

    if not request.POST.has_key('old_name'):
        return
    old_name = request.POST['old_name']
    new_name = request.POST['new_name']
    if os.listdir( ''.join([settings.DATA_PATH, 'reports/']) ). \
     count( ''.join([old_name, '_report.csv']) ) == 1:
        os.rename( '%sreports/%s_report.csv' % (settings.DATA_PATH, old_name),
            '%sreports/%s_report.csv' % (settings.DATA_PATH, new_name))
    elif os.listdir( ''.join([settings.DATA_PATH, 'templates/']) ). \
     count( ''.join([old_name, '.yml']) ) == 1:
        os.rename( '%stemplates/%s.yml' % (settings.DATA_PATH, old_name),
            '%stemplates/%s.yml' % (settings.DATA_PATH, new_name))
        os.rename( '%stemplates/%s.xml' % (settings.DATA_PATH, old_name),
            '%stemplates/%s.xml' % (settings.DATA_PATH, new_name))
    elif os.listdir( ''.join([settings.DATA_PATH, 'bal_count_tot/']) ). \
     count( ''.join([old_name, '.yml']) ) == 1:
        os.rename( '%sbal_count_tot/%s.yml' % (settings.DATA_PATH, old_name),
            '%sbal_count_tot/%s.yml' % (settings.DATA_PATH, new_name))
        os.rename( '%sbal_count_tot/%s.xml' % (settings.DATA_PATH, old_name),
            '%sbal_count_tot/%s.xml' % (settings.DATA_PATH, new_name))
    else:
        os.rename( '%stab_aggr/%s.log' % (settings.DATA_PATH, old_name),
            '%stab_aggr/%s.log' % (settings.DATA_PATH, new_name))
        if os.listdir( ''.join([settings.DATA_PATH + 'tab_aggr/']) ). \
         count( ''.join([old_name, '.yml']) ) == 1:
            os.rename( '%stab_aggr/%s.yml' % (settings.DATA_PATH, old_name),
                '%stab_aggr/%s.yml' % (settings.DATA_PATH, new_name))
            os.rename( '%stab_aggr/%s.xml' % (settings.DATA_PATH, old_name),
                '%stab_aggr/%s.xml' % (settings.DATA_PATH, new_name))
    return HttpResponse()

def mark_up( lines ):
    """
    Html-ize the contents of a file so that they display correctly in
     the front end.
    """

    for i in range( len(lines) ):
        lines[i] = lines[i].replace('<', '&lt;')
        lines[i] = lines[i].replace('>', '&gt;')
        lines[i] = lines[i].replace('\t', '   ')
        lines[i] = lines[i].replace('\n', '')
        if i == len(lines) - 1:
            lines[i] = '<li>%s</li></ul>' % lines[i]
            lines[i] = lines[i].replace(' ', '&nbsp;')
            return lines
        else:
            if indent(lines[i]) == -1 or indent(lines[i]) == indent(lines[i+1]):
                lines[i] = '<li>%s</li></br>' % lines[i]
            elif indent(lines[i]) > indent(lines[i + 1]):
                lines[i] = '<li>%s</li></ul></li></br>' % lines[i]
            else:
                lines[i] = ''.join(['<li><a>',lines[i],u' \u25BC</a><ul></br>'])
        lines[i] = lines[i].replace(' ', '&nbsp;')

def indent( str ):
    """
    Helper function for mark_up. Find the combined number of spaces and
     dashes that begin a string.
    """

    if str == '' or str[:3] == '---':
        return -1
    for i in range( len(str) ):
        if str[i] != ' ' and str[i] != '-':
            return i

def get_file_data():
    """
    Get and categorize all the files created by this system, so that a
     list of them broken down by category can be displayed in the front
     end.
    """

    # Make the subdirectory specified by DATA_PATH within the
    #  directory DATA_PARENT, if it does not exist already. Generated
    #  test data files will go here.    
    if os.listdir(settings.DATA_PARENT).count(settings.DATA_FOLDER) == 0:
        os.mkdir(settings.DATA_PATH)
    if os.listdir(settings.DATA_PATH).count('templates') == 0:
        os.mkdir( ''.join([settings.DATA_PATH, 'templates/']) )
    if os.listdir(settings.DATA_PATH).count('bal_count_tot') == 0:
        os.mkdir( ''.join([settings.DATA_PATH, 'bal_count_tot/']) )
    if os.listdir(settings.DATA_PATH).count('tab_aggr') == 0:
        os.mkdir( ''.join([settings.DATA_PATH, 'tab_aggr/']) )
    if os.listdir(settings.DATA_PATH).count('reports') == 0:
        os.mkdir( ''.join([settings.DATA_PATH, 'reports/']) )

    # Get a list of files so far generated, by type. Leave off the .yml
    #  and .xml file extensions, as well as redundancies.
    templates = os.listdir( ''.join([settings.DATA_PATH, 'templates/']) )
    juris_files = []
    prec_files = []
    for i in range(0, len(templates)):
        if templates[i][len(templates[i]) - len('.yml'):] == '.yml':
            a = audit_header.AuditHeader()
            with open( '%stemplates/%s' % (settings.DATA_PATH,
             templates[i]),'r' ) as s:
                a.load_from_file(s)
            if a.type == 'jurisdiction_slate':
                juris_files.append \
                 (templates[i][:len(templates[i]) - len('.yml')])
            else:
                prec_files.append \
                 (templates[i][:len(templates[i]) - len('.yml')])
        templates[i] = templates[i][:templates[i].rfind('.')]
    template_files = set(templates)
    bal_files = os.listdir( ''.join([settings.DATA_PATH, 'bal_count_tot/']) )
    for i in range(0, len(bal_files)):
        bal_files[i] = bal_files[i][:bal_files[i].rfind('.')]
    bal_files = set(bal_files)
    tab_files = os.listdir( ''.join([settings.DATA_PATH + 'tab_aggr/']) )
    for i in range(0, len(tab_files)):
        tab_files[i] = tab_files[i][:tab_files[i].rfind('.')]
    no_log_files = []
    for i in tab_files:
        if tab_files.count(i) != 1:
            no_log_files.append(i)
    no_log_files = set(no_log_files)
    tab_files = set(tab_files)
    report_files = os.listdir( ''.join([settings.DATA_PATH, 'reports/']) )
    for i in range(0, len(report_files)):
        report_files[i] = report_files[i][:report_files[i].rfind('_report')]
    report_files = set(report_files)

    tdg_files = set(prec_files).union(set(juris_files)).union(bal_files)
    merge_files = bal_files.union(no_log_files)    

    # Get version / last revision info from file
    with open('VERSION', 'r') as stream:
        version = stream.readlines()

    return Context({'prec_files':prec_files, 'juris_files':juris_files,
                    'bal_files':bal_files, 'tdg_files':tdg_files,
                    'tab_files':tab_files, 'merge_files':merge_files,
                    'report_files':report_files, 'no_log_files': no_log_files,
                    'template_files':template_files, 'version':version})

def settings_processor(request):
    return {'ROOT':settings.SITE_ROOT, 'HOME':settings.LOGIN_URL}
