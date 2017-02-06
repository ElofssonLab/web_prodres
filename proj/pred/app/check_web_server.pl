#!/usr/bin/perl -w
# Filename:   check_web_server.pl

# Description: check whether web-server is accessable and also check the status
#              of the qd_fe.py

# Created 2017-02-05, updated 2017-02-05, Nanjiang Shu

use File::Temp;

use Cwd 'abs_path';
use File::Basename;

use LWP::Simple qw($ua head);
$ua->timeout(10);

my $rundir = dirname(abs_path(__FILE__));
my $basedir = "$rundir/../";
require "$rundir/nanjianglib.pl";

my @to_email_list = (
    "nanjiang.shu\@gmail.com");

my $date = localtime();
print "Date: $date\n";
my @urllist = ("http://prodres.bioinfo.se");
my $target_qd_script_name = "qd_fe.py";
my $computenodelistfile = "$basedir/static/computenode.txt";
my $from_email = "nanjiang.shu\@scilifelab.se";
my $title = "";
my $output = "";

foreach my $url (@urllist){ 
# first: check if $url is accessable
    if (!head($url)){
        $title = "$url un-accessible";
        $output = "$url un-accessible";
        foreach my $to_email(@to_email_list) {
            sendmail($to_email, $from_email, $title, $output);
        }
    }

# second: check if qd_topcons2_fe.pl running at pcons1.scilifelab.se frontend
    my $num_running=`curl $url/cgi-bin/check_qd_fe.cgi 2> /dev/null | html2text | grep  "$target_qd_script_name" | wc -l`;
    chomp($num_running);

    if ($num_running < 1){
        $output=`curl $url/cgi-bin/restart_qd_fe.cgi 2>&1 | html2text`;
        $title = "$target_qd_script_name restarted for $url";
        foreach my $to_email(@to_email_list) {
            sendmail($to_email, $from_email, $title, $output);
        }
    }
}

# third, check if the suq queue is blocked at the compute node and try to clean
# it if blocked
my @computenodelist = ();
open(IN, "<", $computenodelistfile) or die;
while(<IN>) {
    chomp;
    push @computenodelist, $_;
}
close IN;
foreach my $computenode(@computenodelist){
    print "curl http://$computenode/cgi-bin/clean_blocked_suq.cgi 2>&1 | html2text\n";
    $output=`curl http://$computenode/cgi-bin/clean_blocked_suq.cgi 2>&1 | html2text`;
    `curl http://$computenode/cgi-bin/set_suqntask.cgi?ntask=5 `;
    if ($output =~ /Try to clean the queue/){
        $title = "Cleaning the queue at $computenode";
        foreach my $to_email(@to_email_list) {
            sendmail($to_email, $from_email, $title, $output);
        }
    }
}