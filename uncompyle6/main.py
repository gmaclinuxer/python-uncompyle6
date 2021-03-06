from __future__ import print_function
import datetime, os, sys

from uncompyle6 import verify, PYTHON_VERSION, IS_PYPY
from xdis.code import iscode
from uncompyle6.disas import check_object_path
from uncompyle6.semantics import pysource
from uncompyle6.parser import ParserError

from xdis.load import load_module

def uncompyle(
        version, co, out=None, showasm=False, showast=False,
        timestamp=None, showgrammar=False, code_objects={},
        is_pypy=False, magic_int=None):
    """
    ingests and deparses a given code block 'co'
    """
    assert iscode(co)

    # store final output stream for case of error
    real_out = out or sys.stdout
    co_pypy_str = 'PyPy ' if is_pypy else ''
    run_pypy_str = 'PyPy ' if IS_PYPY else ''
    print('# %sPython bytecode %s%s disassembled from %sPython %s' %
          (co_pypy_str, version,
           " (%d)" % magic_int if magic_int else "",
           run_pypy_str, PYTHON_VERSION),
          file=real_out)
    if co.co_filename:
        print('# Embedded file name: %s' % co.co_filename,
              file=real_out)
    if timestamp:
        print('# Compiled at: %s' % datetime.datetime.fromtimestamp(timestamp),
              file=real_out)

    try:
        pysource.deparse_code(version, co, out, showasm, showast, showgrammar,
                              code_objects=code_objects, is_pypy=is_pypy)
    except pysource.SourceWalkerError as e:
        # deparsing failed
        print("\n")
        print(co.co_filename)
        if real_out != out:
            print("\n", file=real_out)
            print(e, file=real_out)



def uncompyle_file(filename, outstream=None, showasm=False, showast=False,
                   showgrammar=False):
    """
    decompile Python byte-code file (.pyc)
    """

    filename = check_object_path(filename)
    code_objects = {}
    version, timestamp, magic_int, co, is_pypy = load_module(filename, code_objects)


    if type(co) == list:
        for con in co:
            uncompyle(version, con, outstream, showasm, showast,
                      timestamp, showgrammar, code_objects=code_objects,
                      is_pypy=is_pypy, magic_int=magic_int)
    else:
        uncompyle(version, co, outstream, showasm, showast,
                  timestamp, showgrammar, code_objects=code_objects,
                  is_pypy=is_pypy, magic_int=magic_int)
    co = None

# FIXME: combine into an options parameter
def main(in_base, out_base, files, codes, outfile=None,
         showasm=False, showast=False, do_verify=False,
         showgrammar=False, raise_on_error=False):
    """
    in_base	base directory for input files
    out_base	base directory for output files (ignored when
    files	list of filenames to be uncompyled (relative to src_base)
    outfile	write output to this filename (overwrites out_base)

    For redirecting output to
    - <filename>		outfile=<filename> (out_base is ignored)
    - files below out_base	out_base=...
    - stdout			out_base=None, outfile=None
    """
    def _get_outstream(outfile):
        dir = os.path.dirname(outfile)
        failed_file = outfile + '_failed'
        if os.path.exists(failed_file):
            os.remove(failed_file)
        try:
            os.makedirs(dir)
        except OSError:
            pass
        return open(outfile, 'w')

    of = outfile
    tot_files = okay_files = failed_files = verify_failed_files = 0

    # for code in codes:
    #    version = sys.version[:3] # "2.5"
    #    with open(code, "r") as f:
    #        co = compile(f.read(), "", "exec")
    #    uncompyle(sys.version[:3], co, sys.stdout, showasm=showasm, showast=showast)

    for filename in files:
        infile = os.path.join(in_base, filename)
        if not os.path.exists(infile):
            sys.stderr.write("File '%s' doesn't exist. Skipped\n"
                             % infile)
            continue

        # print (infile, file=sys.stderr)

        if of: # outfile was given as parameter
            outstream = _get_outstream(outfile)
        elif out_base is None:
            outstream = sys.stdout
        else:
            outfile = os.path.join(out_base, filename) + '_dis'
            outstream = _get_outstream(outfile)
        # print(outfile, file=sys.stderr)

        # Try to uncompile the input file
        try:
            uncompyle_file(infile, outstream, showasm, showast, showgrammar)
            tot_files += 1
        except (ValueError, SyntaxError, ParserError) as e:
            sys.stderr.write("\n# file %s\n# %s" % (infile, e))
            failed_files += 1
        except KeyboardInterrupt:
            if outfile:
                outstream.close()
                os.remove(outfile)
            sys.stderr.write("\nLast file: %s   " % (infile))
            raise
        # except:
        #     failed_files += 1
        #     if outfile:
        #         outstream.close()
        #         os.rename(outfile, outfile + '_failed')
        #     else:
        #         sys.stderr.write("\n# %s" % sys.exc_info()[1])
        #         sys.stderr.write("\n# Can't uncompile %s\n" % infile)
        else: # uncompile successful
            if outfile:
                outstream.close()
                if do_verify:
                    weak_verify = do_verify == 'weak'
                    try:
                        msg = verify.compare_code_with_srcfile(infile, outfile, weak_verify=weak_verify)
                        if not outfile:
                            if not msg:
                                print('\n# okay decompiling %s' % infile)
                                okay_files += 1
                            else:
                                print('\n# %s\n\t%s', infile, msg)
                    except verify.VerifyCmpError as e:
                        print(e)
                        verify_failed_files += 1
                        os.rename(outfile, outfile + '_unverified')
                        if not outfile:
                            print("### Error Verifiying %s" % filename,  file=sys.stderr)
                            print(e, file=sys.stderr)
                            if raise_on_error:
                                raise
                            pass
                        pass
                pass
            elif do_verify:
                print("\n### uncompile successful, but no file to compare against",
                      file=sys.stderr)
                pass
            else:
                okay_files += 1
                if not outfile:
                    mess = '\n# okay decompiling'
                    # mem_usage = __memUsage()
                    print(mess, infile)
        if outfile:
            sys.stdout.write("%s\r" %
                             status_msg(do_verify, tot_files, okay_files, failed_files, verify_failed_files))
            sys.stdout.flush()
    if outfile:
        sys.stdout.write("\n")
        sys.stdout.flush()
    return (tot_files, okay_files, failed_files, verify_failed_files)


# ---- main ----

if sys.platform.startswith('linux') and os.uname()[2][:2] in ['2.', '3.', '4.']:
    def __memUsage():
        mi = open('/proc/self/stat', 'r')
        mu = mi.readline().split()[22]
        mi.close()
        return int(mu) / 1000000
else:
    def __memUsage():
        return ''

def status_msg(do_verify, tot_files, okay_files, failed_files,
               verify_failed_files):
    if tot_files == 1:
        if failed_files:
            return "decompile failed"
        elif verify_failed_files:
            return "decompile verify failed"
        else:
            return "Successfully decompiled file"
            pass
        pass
    mess = "decompiled %i files: %i okay, %i failed" % (tot_files, okay_files, failed_files)
    if do_verify:
        mess += (", %i verify failed" % verify_failed_files)
    return mess
