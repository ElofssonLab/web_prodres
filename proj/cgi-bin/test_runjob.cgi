#!/usr/bin/perl -w
# test runjob

use CGI qw(:standard);
use CGI qw(:cgi-lib);
use CGI qw(:upload);

use Cwd 'abs_path';
use File::Basename;
my $rundir = dirname(abs_path(__FILE__));
# at proj
my $basedir = abs_path("$rundir/../pred");
my $progname = basename(__FILE__);
my $logpath = "$basedir/static/log";
my $errfile = "$logpath/$progname.err";
my $auth_ip_file = "$basedir/config/auth_iplist.txt";#ip address which allows to run cgi script
my $suq = "/usr/bin/suq";
my $suqbase = "/scratch";
my $suqworkdir = "/scratch";

my $runjobscript = "$basedir/app/run_job.py";

print header();
print start_html(-title => "test run job",
    -author => "nanjiang.shu\@scilifelab.se",
    -meta   => {'keywords'=>''});

my $remote_host = $ENV{'REMOTE_ADDR'};

my @auth_iplist = ();
open(IN, "<", $auth_ip_file) or die;
while(<IN>) {
    chomp;
    push @auth_iplist, $_;
}
close IN;

if (grep { $_ eq $remote_host } @auth_iplist) {
    my $command =  "$suq -b $suqbase run -d $suqworkdir $runjobscript >>$errfile";
    $output = `$command`;
    print "<pre>";
    print "Host IP: $remote_host\n\n";
    print "command: $command\n\n";
    print "Suq list:\n\n";
    print "$output\n";

    print "</pre>";
}else{
    print "Permission denied!\n";
}

print '<br>';
print end_html();

