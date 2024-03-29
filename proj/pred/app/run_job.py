#!/usr/bin/env python
# Description: run job
import os
import sys
import subprocess
import time
from libpredweb import myfunc
from libpredweb import webserver_common as webcom
import glob
import hashlib
import shutil
import site
import fcntl
import json
progname =  os.path.basename(sys.argv[0])
wspace = ''.join([" "]*len(progname))
rundir = os.path.dirname(os.path.realpath(__file__))
webserver_root = os.path.realpath("%s/../../../"%(rundir))
activate_env="%s/env/bin/activate_this.py"%(webserver_root)
exec(compile(open(activate_env, "rb").read(), activate_env, 'exec'), dict(__file__=activate_env))

site.addsitedir("%s/env/lib/python2.7/site-packages/"%(webserver_root))
sys.path.append("/usr/local/lib/python2.7/dist-packages")

path_pfamscan = "%s/misc/PfamScan"%(webserver_root)
path_pfamdatabase = "%s/soft/PRODRES/databases"%(rundir)
path_pfamscanscript = "%s/pfam_scan.pl"%(path_pfamscan)
blastdb = "%s/soft/PRODRES/databases/blastdb/uniref90.fasta"%(rundir)
if 'PERL5LIB' not in os.environ:
    os.environ['PERL5LIB'] = ""
os.environ['PERL5LIB'] = os.environ['PERL5LIB'] + ":" + path_pfamscan
runscript = "%s/%s"%(rundir, "soft/PRODRES/PRODRES/PRODRES.py")
#runscript = "%s/%s"%(rundir, "soft/dummyrun.sh")

basedir = os.path.realpath("%s/.."%(rundir)) # path of the application, i.e. pred/
path_cache = "%s/static/result/cache"%(basedir)
path_result = "%s/static/result/"%(basedir)
path_log = "%s/static/log"%(basedir)
finished_date_db = "%s/cached_job_finished_date.sqlite3"%(path_log)


gen_errfile = "%s/static/log/%s.err"%(basedir, progname)
gen_logfile = "%s/static/log/%s.log"%(basedir, progname)

contact_email = "nanjiang.shu@scilifelab.se"
vip_user_list = [
        "nanjiang.shu@scilifelab.se"
        ]

# note that here the url should be without http://

usage_short="""
Usage: %s seqfile_in_fasta 
       %s -jobid JOBID -outpath DIR -tmpdir DIR
       %s -email EMAIL -baseurl BASE_WWW_URL
       %s -only-get-cache [-force]
"""%(progname, wspace, wspace, wspace)

usage_ext="""\
Description:
    run job

OPTIONS:
  -only-get-cache   Only get the cached results, this will be run on the front-end
  -force            Do not use cahced result
  -h, --help        Print this help message and exit

Created 2016-12-01, 2018-10-11, Nanjiang Shu
"""
usage_exp="""
Examples:
    %s /data3/tmp/tmp_dkgSD/query.fa -outpath /data3/result/rst_mXLDGD -tmpdir /data3/tmp/tmp_dkgSD
"""%(progname)

def PrintHelp(fpout=sys.stdout):#{{{
    print(usage_short, file=fpout)
    print(usage_ext, file=fpout)
    print(usage_exp, file=fpout)#}}}

def RunJob(infile, outpath, tmpdir, email, jobid, g_params):#{{{
    all_begin_time = time.time()

    rootname = os.path.basename(os.path.splitext(infile)[0])
    starttagfile   = "%s/runjob.start"%(outpath)
    runjob_errfile = "%s/runjob.err"%(outpath)
    runjob_logfile = "%s/runjob.log"%(outpath)
    app_logfile = "%s/app.log"%(outpath)
    finishtagfile = "%s/runjob.finish"%(outpath)
    failedtagfile = "%s/runjob.failed"%(outpath)
    query_parafile = "%s/query.para.txt"%(outpath)

    query_para = ""
    content = myfunc.ReadFile(query_parafile)
    if content != "":
        query_para = json.loads(content)

    rmsg = ""

    resultpathname = jobid

    outpath_result = "%s/%s"%(outpath, resultpathname)
    tmp_outpath_result = "%s/%s"%(tmpdir, resultpathname)

    tarball = "%s.tar.gz"%(resultpathname)
    zipfile = "%s.zip"%(resultpathname)
    tarball_fullpath = "%s.tar.gz"%(outpath_result)
    zipfile_fullpath = "%s.zip"%(outpath_result)
    resultfile_text = "%s/%s"%(outpath_result, "query.result.txt")
    mapfile = "%s/seqid_index_map.txt"%(outpath_result)
    finished_seq_file = "%s/finished_seqs.txt"%(outpath_result)

    for folder in [outpath_result, tmp_outpath_result]:
        try:
            os.makedirs(folder)
        except OSError:
            msg = "Failed to create folder %s"%(folder)
            myfunc.WriteFile(msg+"\n", gen_errfile, "a")
            return 1
    try:
        open(finished_seq_file, 'w').close()
    except:
        pass
#first getting result from caches
# ==================================

    maplist = []
    maplist_simple = []
    toRunDict = {}
    hdl = myfunc.ReadFastaByBlock(infile, method_seqid=0, method_seq=0)
    if hdl.failure:
        isOK = False
    else:
        webcom.WriteDateTimeTagFile(starttagfile, runjob_logfile, runjob_errfile)
        recordList = hdl.readseq()
        cnt = 0
        origpath = os.getcwd()
        while recordList != None:
            for rd in recordList:
                isSkip = False
                # temp outpath for the sequence is always seq_0, and I feed
                # only one seq a time to the workflow
                tmp_outpath_this_seq = "%s/%s"%(tmp_outpath_result, "seq_%d"%0)
                outpath_this_seq = "%s/%s"%(outpath_result, "seq_%d"%cnt)
                subfoldername_this_seq = "seq_%d"%(cnt)
                if os.path.exists(tmp_outpath_this_seq):
                    try:
                        shutil.rmtree(tmp_outpath_this_seq)
                    except OSError:
                        pass

                maplist.append("%s\t%d\t%s\t%s"%("seq_%d"%cnt, len(rd.seq),
                    rd.description, rd.seq))
                maplist_simple.append("%s\t%d\t%s"%("seq_%d"%cnt, len(rd.seq),
                    rd.description))
                if not g_params['isForceRun']:
                    md5_key = hashlib.md5((rd.seq+str(query_para)).encode('utf-8')).hexdigest()
                    subfoldername = md5_key[:2]
                    cachedir = "%s/%s/%s"%(path_cache, subfoldername, md5_key)
                    zipfile_cache = cachedir + ".zip"

                    if os.path.exists(cachedir) or os.path.exists(zipfile_cache):
                        if os.path.exists(cachedir):
                            try:
                                shutil.copytree(cachedir, outpath_this_seq)
                            except Exception as e:
                                msg = "Failed to copytree  %s -> %s"%(cachedir, outpath_this_seq)
                                date_str = time.strftime(FORMAT_DATETIME)
                                myfunc.WriteFile("[%s] %s with errmsg=%s\n"%(date_str, 
                                    msg, str(e)), runjob_errfile, "a")
                        elif os.path.exists(zipfile_cache):
                            cmd = ["unzip", zipfile_cache, "-d", outpath_result]
                            webcom.RunCmd(cmd, runjob_logfile, runjob_errfile)
                            shutil.move("%s/%s"%(outpath_result, md5_key), outpath_this_seq)

                        if os.path.exists(outpath_this_seq):
                            info_finish = webcom.GetInfoFinish_PRODRES(outpath_this_seq,
                                    cnt, len(rd.seq), rd.description, source_result="cached", runtime=0.0)
                            myfunc.WriteFile("\t".join(info_finish)+"\n",
                                    finished_seq_file, "a", isFlush=True)
                            isSkip = True

                if not isSkip:
                    # first try to delete the outfolder if exists
                    if os.path.exists(outpath_this_seq):
                        try:
                            shutil.rmtree(outpath_this_seq)
                        except OSError:
                            pass
                    origIndex = cnt
                    numTM = 0
                    toRunDict[origIndex] = [rd.seq, numTM, rd.description] #init value for numTM is 0

                cnt += 1
            recordList = hdl.readseq()
        hdl.close()
    myfunc.WriteFile("\n".join(maplist_simple)+"\n", mapfile)


    if not g_params['isOnlyGetCache']:
        torun_all_seqfile = "%s/%s"%(tmp_outpath_result, "query.torun.fa")
        dumplist = []
        for key in toRunDict:
            top = toRunDict[key][0]
            dumplist.append(">%s\n%s"%(str(key), top))
        myfunc.WriteFile("\n".join(dumplist)+"\n", torun_all_seqfile, "w")
        del dumplist


        sortedlist = sorted(list(toRunDict.items()), key=lambda x:x[1][1], reverse=True)
        #format of sortedlist [(origIndex: [seq, numTM, description]), ...]

        # submit sequences one by one to the workflow according to orders in
        # sortedlist

        for item in sortedlist:
            origIndex = item[0]
            seq = item[1][0]
            description = item[1][2]

            subfoldername_this_seq = "seq_%d"%(origIndex)
            outpath_this_seq = "%s/%s"%(outpath_result, subfoldername_this_seq)
            tmp_outpath_this_seq = "%s/%s"%(tmp_outpath_result, "seq_%d"%(0))
            if os.path.exists(tmp_outpath_this_seq):
                try:
                    shutil.rmtree(tmp_outpath_this_seq)
                except OSError:
                    pass

            seqfile_this_seq = "%s/%s"%(tmp_outpath_result, "query_%d.fa"%(origIndex))
            seqcontent = ">query_%d\n%s\n"%(origIndex, seq)
            myfunc.WriteFile(seqcontent, seqfile_this_seq, "w")

            if not os.path.exists(seqfile_this_seq):
                msg = "failed to generate seq index %d"%(origIndex)
                date_str = time.strftime(g_params['FORMAT_DATETIME'])
                myfunc.WriteFile("[%s] %s\n"%(date_str, msg), runjob_errfile, "a", True)
                continue

            cmd = ["python", runscript, "--input", seqfile_this_seq, "--output", tmp_outpath_this_seq, "--pfam-dir", path_pfamdatabase, "--pfamscan-script", path_pfamscanscript, "--fallback-db-fasta", blastdb]

            if 'second_method' in query_para and query_para['second_method'] != "":
                cmd += ['--second-search', query_para['second_method']]

            if 'pfamscan_evalue' in query_para and query_para['pfamscan_evalue'] != "":
                cmd += ['--pfamscan_e-val', query_para['pfamscan_evalue']]
            elif 'pfamscan_bitscore' in query_para and query_para['pfamscan_bitscore'] != "":
                cmd += ['--pfamscan_bitscore', query_para['pfamscan_bitscore']]

            if 'pfamscan_clanoverlap' in query_para:
                if query_para['pfamscan_clanoverlap'] == False:
                    cmd += ['--pfamscan_clan-overlap', 'no']
                else:
                    cmd += ['--pfamscan_clan-overlap', 'yes']

            if 'jackhmmer_iteration' in query_para and query_para['jackhmmer_iteration'] != "":
                cmd += ['--jackhmmer_max_iter', query_para['jackhmmer_iteration']]

            if 'jackhmmer_threshold_type' in query_para and query_para['jackhmmer_threshold_type'] != "":
                cmd += ['--jackhmmer-threshold-type', query_para['jackhmmer_threshold_type']]

            if 'jackhmmer_evalue' in query_para and query_para['jackhmmer_evalue'] != "":
                cmd += ['--jackhmmer_e-val', query_para['jackhmmer_evalue']]
            elif 'jackhmmer_bitscore' in query_para and query_para['jackhmmer_bitscore'] != "":
                cmd += ['--jackhmmer_bit-score', query_para['jackhmmer_bitscore']]

            if 'psiblast_iteration' in query_para and query_para['psiblast_iteration'] != "":
                cmd += ['--psiblast_iter', query_para['psiblast_iteration']]
            if 'psiblast_outfmt' in query_para and query_para['psiblast_outfmt'] != "":
                cmd += ['--psiblast_outfmt', query_para['psiblast_outfmt']]


            (t_success, runtime_in_sec) = webcom.RunCmd(cmd, runjob_logfile, runjob_errfile, True)

            aaseqfile = "%s/seq.fa"%(tmp_outpath_this_seq+os.sep+"query_0")
            if not os.path.exists(aaseqfile):
                seqcontent = ">%s\n%s\n"%(description, seq)
                myfunc.WriteFile(seqcontent, aaseqfile, "w")


            if os.path.exists(tmp_outpath_this_seq):
                cmd = ["mv","-f", tmp_outpath_this_seq+os.sep+"query_0", outpath_this_seq]
                isCmdSuccess = False
                (isCmdSuccess, t_runtime) = webcom.RunCmd(cmd, runjob_logfile, runjob_errfile, True)

                if not 'isKeepTempFile' in query_para or query_para['isKeepTempFile'] == False:
                    try:
                        temp_result_folder = "%s/temp"%(outpath_this_seq)
                        shutil.rmtree(temp_result_folder)
                    except:
                        msg = "Failed to delete the folder %s"%(temp_result_folder)
                        date_str = time.strftime(g_params['FORMAT_DATETIME'])
                        myfunc.WriteFile("[%s] %s\n"%(date_str, msg), runjob_errfile, "a", True)

                    flist = [
                            "%s/outputs/%s"%(outpath_this_seq, "Alignment.txt"),
                            "%s/outputs/%s"%(outpath_this_seq, "tableOut.txt"),
                            "%s/outputs/%s"%(outpath_this_seq, "fullOut.txt")
                            ]
                    for f in flist:
                        if os.path.exists(f):
                            try:
                                os.remove(f)
                            except:
                                msg = "Failed to delete the file %s"%(f)
                                date_str = time.strftime(g_params['FORMAT_DATETIME'])
                                myfunc.WriteFile("[%s] %s\n"%(date_str, msg), runjob_errfile, "a", True)

                if isCmdSuccess:
                    timefile = "%s/time.txt"%(outpath_this_seq)
                    runtime = webcom.ReadRuntimeFromFile(timefile, default_runtime=0.0)
                    info_finish = webcom.GetInfoFinish_PRODRES(outpath_this_seq,
                            origIndex, len(seq), description, source_result="newrun", runtime=runtime)
                    myfunc.WriteFile("\t".join(info_finish)+"\n",
                            finished_seq_file, "a", isFlush=True)
                    # now write the text output for this seq

                    info_this_seq = "%s\t%d\t%s\t%s"%("seq_%d"%origIndex, len(seq), description, seq)
                    resultfile_text_this_seq = "%s/%s"%(outpath_this_seq, "query.result.txt")
                    #webcom.WriteSubconsTextResultFile(resultfile_text_this_seq,
                    #        outpath_result, [info_this_seq], runtime_in_sec, g_params['base_www_url'])
                    # create or update the md5 cache
                    # create cache only on the front-end
                    if webcom.IsFrontEndNode(g_params['base_www_url']):
                        md5_key = hashlib.md5((seq+str(query_para)).encode('utf-8')).hexdigest()
                        subfoldername = md5_key[:2]
                        md5_subfolder = "%s/%s"%(path_cache, subfoldername)
                        cachedir = "%s/%s/%s"%(path_cache, subfoldername, md5_key)

                        # copy the zipped folder to the cache path
                        origpath = os.getcwd()
                        os.chdir(outpath_result)
                        shutil.copytree("seq_%d"%(origIndex), md5_key)
                        cmd = ["zip", "-rq", "%s.zip"%(md5_key), md5_key]
                        webcom.RunCmd(cmd, runjob_logfile, runjob_logfile)
                        if not os.path.exists(md5_subfolder):
                            os.makedirs(md5_subfolder)
                        shutil.move("%s.zip"%(md5_key), "%s.zip"%(cachedir))
                        shutil.rmtree(md5_key) # delete the temp folder named as md5 hash
                        os.chdir(origpath)

                        # Add the finished date to the database
                        date_str = time.strftime(FORMAT_DATETIME)
                        webcom.InsertFinishDateToDB(date_str, md5_key, seq, finished_date_db)



    all_end_time = time.time()
    all_runtime_in_sec = all_end_time - all_begin_time

    if not g_params['isOnlyGetCache'] or len(toRunDict) == 0:
        # now write the text output to a single file
        statfile = "%s/%s"%(outpath_result, "stat.txt")
        #webcom.WriteSubconsTextResultFile(resultfile_text, outpath_result, maplist,
        #        all_runtime_in_sec, g_params['base_www_url'], statfile=statfile)

        # now making zip instead (for windows users)
        # note that zip rq will zip the real data for symbolic links
        os.chdir(outpath)
#             cmd = ["tar", "-czf", tarball, resultpathname]
        cmd = ["zip", "-rq", zipfile, resultpathname]
        webcom.RunCmd(cmd, runjob_logfile, runjob_errfile)

        # write finish tag file
        if os.path.exists(finished_seq_file):
            webcom.WriteDateTimeTagFile(finishtagfile, runjob_logfile, runjob_errfile)

        isSuccess = False
        if (os.path.exists(finishtagfile) and os.path.exists(zipfile_fullpath)):
            isSuccess = True
        else:
            isSuccess = False
            webcom.WriteDateTimeTagFile(failedtagfile, runjob_logfile, runjob_errfile)


# send the result to email
# do not sendmail at the cloud VM
        if webcom.IsFrontEndNode(g_params['base_www_url']) and myfunc.IsValidEmailAddress(email):
            if isSuccess:
                finish_status = "success"
            else:
                finish_status = "failed"
            webcom.SendEmail_on_finish(jobid, g_params['base_www_url'],
                    finish_status, name_server="PRODRES", from_email="no-reply.PRODRES@bioinfo.se",
                    to_email=email, contact_email=contact_email,
                    logfile=runjob_logfile, errfile=runjob_errfile)

    if os.path.exists(runjob_errfile) and os.path.getsize(runjob_errfile) > 1:
        return 1
    else:
        try:
            shutil.rmtree(tmpdir)
            msg = "rmtree(%s)"%(tmpdir)
            webcom.loginfo("rmtree(%s)"%(tmpdir), runjob_logfile)
        except Exception as e:
            msg = "Failed to rmtree(%s)"%(tmpdir)
            webcom.loginfo("Failed to rmtree(%s) with error message: %s"%(tmpdir, str(e)), runjob_errfile)
        return 0
#}}}
def main(g_params):#{{{
    argv = sys.argv
    numArgv = len(argv)
    if numArgv < 2:
        PrintHelp()
        return 1

    outpath = ""
    infile = ""
    tmpdir = ""
    email = ""
    jobid = ""

    i = 1
    isNonOptionArg=False
    while i < numArgv:
        if isNonOptionArg == True:
            infile = argv[i]
            isNonOptionArg = False
            i += 1
        elif argv[i] == "--":
            isNonOptionArg = True
            i += 1
        elif argv[i][0] == "-":
            if argv[i] in ["-h", "--help"]:
                PrintHelp()
                return 1
            elif argv[i] in ["-outpath", "--outpath"]:
                (outpath, i) = myfunc.my_getopt_str(argv, i)
            elif argv[i] in ["-tmpdir", "--tmpdir"] :
                (tmpdir, i) = myfunc.my_getopt_str(argv, i)
            elif argv[i] in ["-jobid", "--jobid"] :
                (jobid, i) = myfunc.my_getopt_str(argv, i)
            elif argv[i] in ["-baseurl", "--baseurl"] :
                (g_params['base_www_url'], i) = myfunc.my_getopt_str(argv, i)
            elif argv[i] in ["-email", "--email"] :
                (email, i) = myfunc.my_getopt_str(argv, i)
            elif argv[i] in ["-q", "--q"]:
                g_params['isQuiet'] = True
                i += 1
            elif argv[i] in ["-force", "--force"]:
                g_params['isForceRun'] = True
                i += 1
            elif argv[i] in ["-only-get-cache", "--only-get-cache"]:
                g_params['isOnlyGetCache'] = True
                i += 1
            else:
                print("Error! Wrong argument:", argv[i], file=sys.stderr)
                return 1
        else:
            infile = argv[i]
            i += 1

    if jobid == "":
        print("%s: jobid not set. exit"%(sys.argv[0]), file=sys.stderr)
        return 1

    # create a lock file in the resultpath when run_job.py is running for this
    # job, so that daemon will not run on this folder
    lockname = "runjob.lock"
    lock_file = "%s/%s/%s"%(path_result, jobid, lockname)
    g_params['lockfile'] = lock_file
    fp = open(lock_file, 'w')
    try:
        fcntl.lockf(fp, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except IOError:
        print("Another instance of %s is running"%(progname), file=sys.stderr)
        return 1


    if myfunc.checkfile(infile, "infile") != 0:
        return 1
    if outpath == "":
        print("outpath not set. exit", file=sys.stderr)
        return 1
    elif not os.path.exists(outpath):
        try:
            subprocess.check_output(["mkdir", "-p", outpath])
        except subprocess.CalledProcessError as e:
            print(e, file=sys.stderr)
            return 1
    if tmpdir == "":
        print("tmpdir not set. exit", file=sys.stderr)
        return 1
    elif not os.path.exists(tmpdir):
        try:
            subprocess.check_output(["mkdir", "-p", tmpdir])
        except subprocess.CalledProcessError as e:
            print(e, file=sys.stderr)
            return 1

    numseq = myfunc.CountFastaSeq(infile)
    g_params['debugfile'] = "%s/debug.log"%(outpath)
    return RunJob(infile, outpath, tmpdir, email, jobid, g_params)

#}}}

def InitGlobalParameter():#{{{
    g_params = {}
    g_params['isQuiet'] = True
    g_params['isForceRun'] = False
    g_params['isOnlyGetCache'] = False
    g_params['base_www_url'] = ""
    g_params['lockfile'] = ""
    g_params['FORMAT_DATETIME'] = webcom.FORMAT_DATETIME
    return g_params
#}}}
if __name__ == '__main__' :
    g_params = InitGlobalParameter()
    status = main(g_params)
    if os.path.exists(g_params['lockfile']):
        try:
            os.remove(g_params['lockfile'])
        except:
            myfunc.WriteFile("Failed to delete lockfile %s\n"%(g_params['lockfile']), gen_errfile, "a", True)

    sys.exit(status)
