#!/usr/bin/perl
###############################################################################
#                                                                             #
# IPFire.org - A linux based firewall                                         #
# Copyright (C) 2007-2020  IPFire Team  <info@ipfire.org>                     #
# Copyright (C) 2024  BPFire <vincent.mc.li@gmail.com>                     #
#                                                                             #
# This program is free software: you can redistribute it and/or modify        #
# it under the terms of the GNU General Public License as published by        #
# the Free Software Foundation, either version 3 of the License, or           #
# (at your option) any later version.                                         #
#                                                                             #
# This program is distributed in the hope that it will be useful,             #
# but WITHOUT ANY WARRANTY; without even the implied warranty of              #
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the               #
# GNU General Public License for more details.                                #
#                                                                             #
# You should have received a copy of the GNU General Public License           #
# along with this program.  If not, see <http://www.gnu.org/licenses/>.       #
#                                                                             #
###############################################################################

use strict;

# enable only the following on debugging purpose
use warnings;
use CGI::Carp 'fatalsToBrowser';

use IO::Socket;

require '/var/ipfire/general-functions.pl';
require "${General::swroot}/location-functions.pl";
require "${General::swroot}/lang.pl";
require "${General::swroot}/header.pl";

#workaround to suppress a warning when a variable is used only once
my @dummy = ( ${Header::colouryellow} );
undef (@dummy);

my %color = ();
my %mainsettings = ();
my %settings=();
my %checked=();
my $errormessage='';
my $setting = "${General::swroot}/main/settings";
my $loxilbsettingfile = "${General::swroot}/loxilb/settings";
my $loxilbipfile = "${General::swroot}/loxilb/ipconfig";

# Read configuration file.

&General::readhash("${General::swroot}/main/settings", \%mainsettings);
&General::readhash("/srv/web/ipfire/html/themes/ipfire/include/colors.txt", \%color);

&Header::showhttpheaders();

$settings{'ENABLE_LOXILB'} = 'off';
$settings{'ACTION'} = '';

$settings{'KEY1'} = '';                 # point record for ACTION
$settings{'virtualIP'} = '';
$settings{'interface'} = '';
my @nosaved=('virtualIP','interface', 'KEY1', 'SORT_virtualIPLIST');

#Define each field that can be used to sort columns
my $sortstring='^virtualIP';
$settings{'SORT_virtualIPLIST'} = 'virtualIP';

# Load multiline data
our @current = ();
if (open(FILE, "$loxilbipfile")) {
    @current = <FILE>;
    close (FILE);
}

&Header::getcgihash(\%settings);

if ($settings{'ACTION'} eq $Lang::tr{'save'})
{

	map (delete ($settings{$_}) ,(@nosaved));
	&General::writehash("$loxilbsettingfile", \%settings);

	if ($settings{'ENABLE_LOXILB'} eq 'on') {
		&General::system('/usr/bin/touch', "${General::swroot}/loxilb/enableloxilb");
		&General::system('/usr/local/bin/loxilbctrl', 'start');
	} else {
		&General::system('/usr/local/bin/loxilbctrl', 'stop');
		unlink "${General::swroot}/loxilb/enableloxilb";
	}

}

if ($settings{'ACTION'} eq $Lang::tr{'add'}) {
        # Validate inputs
        if (!&General::validipandmask($settings{'virtualIP'})){
                $errormessage = $Lang::tr{'invalid ip'}." / ".$Lang::tr{'invalid netmask'};
        }

        #Check for already existing routing entry
        foreach my $line (@current) {
                chomp($line);                           # remove newline
                my @temp=split(/\,/,$line);
                $temp[1] ='' unless defined $temp[1]; # interface
                #Same ip already used?
                if($temp[0] eq $settings{'virtualIP'} && $settings{'KEY1'} eq ''){
                        $errormessage = $Lang::tr{'ccd err loxilbconfigeexist'};
                        last;
                }
        }

    unless ($errormessage) {
        if ($settings{'KEY1'} eq '') { #add or edit ?
            unshift (@current, "$settings{'virtualIP'},$settings{'interface'}\n");
            &General::log($Lang::tr{'loxilb lb config added'});
        } else {
            @current[$settings{'KEY1'}] = "$settings{'virtualIP'},$settings{'interface'}\n";
            $settings{'KEY1'} = '';       # End edit mode
            &General::log($Lang::tr{'loxilb fw changed'});
        }

        &CreateIP(%settings);

        # Write changes to config file.
        &SortDataFile;                          # sort newly added/modified entry

        #map ($settings{$_}='' ,@nosaved);      # Clear fields
    }
}

if ($settings{'ACTION'} eq $Lang::tr{'remove'}) {

    my $line = @current[$settings{'KEY1'}];     # KEY1 is the index in current
    chomp($line);
    my @temp = split(/\,/, $line);
    $settings{'virtualIP'}=$temp[0];
    $settings{'interface'}=$temp[1];

    &DeleteIP(%settings);

    splice (@current,$settings{'KEY1'},1);              # Delete line
    open(FILE, ">$loxilbipfile") or die "$loxilbipfile open error";
    print FILE @current;
    close(FILE);
    $settings{'KEY1'} = '';                             # End remove mode
}

##  Check if sorting is asked
# If same column clicked, reverse the sort.
if ($ENV{'QUERY_STRING'} =~ /$sortstring/ ) {
    my $newsort=$ENV{'QUERY_STRING'};
    my $actual=$settings{'SORT_virtualIPLIST'};
    #Reverse actual sort ?
    if ($actual =~ $newsort) {
        my $Rev='';
        if ($actual !~ 'Rev') {
            $Rev='Rev';
        }
        $newsort.=$Rev;
    }
    $settings{'SORT_virtualIPLIST'}=$newsort;
    map (delete ($settings{$_}) ,(@nosaved,'ACTION','KEY1'));# Must never be saved
    &General::writehash($setting, \%settings);
    &SortDataFile;
    $settings{'ACTION'} = 'SORT';                       # Create an 'ACTION'
    map ($settings{$_} = '' ,@nosaved,'KEY1');          # and reinit vars to empty
}

if ($settings{'ACTION'} eq '' ) { # First launch from GUI
    # Place here default value when nothing is initialized
    $settings{'virtualIP'} = '';
    $settings{'interface'} = '';
}

&Header::openpage($Lang::tr{'loxilb'}, 1, '');

&Header::openbigbox('100%', 'left', '', $errormessage);

if ($errormessage) {
	&Header::openbox('100%', 'left', $Lang::tr{'error messages'});
	print "<font class='base' color=red>$errormessage&nbsp;</font>\n";
	&Header::closebox();
}

# Read configuration file.
&General::readhash("$loxilbsettingfile", \%settings);

# Checkbox pre-selection.
my $checked;
if ($settings{'ENABLE_LOXILB'} eq "on") {
        $checked = "checked='checked'";
}

my $sactive = "<table cellpadding='2' cellspacing='0' bgcolor='${Header::colourred}' width='50%'><tr><td align='center'><b><font color='#FFFFFF'>$Lang::tr{'stopped'}</font></b></td></tr></table>";

my @status = &General::system_output('/usr/local/bin/loxilbctrl', 'status');

if (grep(/is running/, @status)){
        $sactive = "<table cellpadding='2' cellspacing='0' bgcolor='${Header::colourgreen}' width='50%'><tr><td align='center'><b><font color='#FFFFFF'>$Lang::tr{'running'}</font></b></td></tr></table>";
}

&Header::openbox('100%', 'center', $Lang::tr{'loxilb status'});

print <<END;
        <table width='100%'>
	<form method='POST' action='$ENV{'SCRIPT_NAME'}'>
	<td width='25%'>&nbsp;</td>
	<td width='25%'>&nbsp;</td>
	<td width='25%'>&nbsp;</td>
	<tr><td class='boldbase'>$Lang::tr{'loxilb server status'}</td>
	<td align='left'>$sactive</td>
	</tr>
	<tr>
	<td width='50%' class='boldbase'>$Lang::tr{'loxilb enable'}
	<td><input type='checkbox' name='ENABLE_LOXILB' $checked></td>
	<td align='center'><input type='submit' name='ACTION' value='$Lang::tr{'save'}'></td>
	</tr>
END

print "</form> </table>\n";

&Header::closebox();
#

my $buttontext = $Lang::tr{'add'};
if ($settings{'KEY1'} ne '') {
    $buttontext = $Lang::tr{'update'};
    &Header::openbox('100%', 'left', $Lang::tr{'loxilb fw edit'});
} else {
    &Header::openbox('100%', 'left', $Lang::tr{'loxilb ip add'});
}

my @INTERFACES = ("red0", "green0");

#Edited line number (KEY1) passed until cleared by 'save' or 'remove' or 'new sort order'
print <<END;
<form method='post' action='$ENV{'SCRIPT_NAME'}'>
<input type='hidden' name='KEY1' value='$settings{'KEY1'}' />
<table width='100%'>
<tr>
    <td class='base'>$Lang::tr{'loxilb ip virtualIP'}:&nbsp;</td>
    <td><input type='text' name='virtualIP' value='$settings{'virtualIP'}' size='25'/></td>
</tr>
<tr>
    <td class='base'>$Lang::tr{'loxilb ip interface'}:&nbsp;</td>
    <td>
      <select name='interface' id='interface' style="width: 95px;">
END

# Insert the dynamic options for the 'PROTO' select element
  foreach (@INTERFACES) {
    print "<option value=\"$_\"";
    if ($_ eq $settings{'interface'}) {
        print " selected=\"selected\"";
    }
    print ">$_</option>";
  }

print <<END;

     </select>
     </td>
</tr>
</table>
<br>
<table width='100%'>
<tr>
    <td width='50%' align='right'><input type='hidden' name='ACTION' value='$Lang::tr{'add'}' /><input type='submit' name='SUBMIT' value='$buttontext' /></td>
</tr>
</table>
</form>
END

&Header::closebox();

&Header::openbox('100%', 'left', $Lang::tr{'loxilb ip entries'});

print <<END;

<table width='100%' class='tbl'>
<tr>
    <th width='10%' align='center'><a href='$ENV{'SCRIPT_NAME'}?virtualIP'><b>$Lang::tr{'loxilb ip virtualIP'}</b></a></th>
    <th width='10%' align='center'><a href='$ENV{'SCRIPT_NAME'}?interface'><b>$Lang::tr{'loxilb ip interface'}</b></a></th>
    <th width='10%' colspan='3' class='boldbase' align='center'><b>$Lang::tr{'action'}</b></th>
</tr>
END

#
# Print each line of @current list
#

my $key = 0;
my $col="";
foreach my $line (@current) {
    chomp($line);                               # remove newline
    my @temp=split(/\,/,$line);
    $temp[1] ='' unless defined $temp[1]; # not always populated

    #Choose icon for checkbox
    my $gif = '';
    my $gdesc = '';
    if ($temp[0] ne '' ) {
        $gif = 'on.gif';
        $gdesc = $Lang::tr{'click to disable'};
    } else {
        $gif = 'off.gif';
        $gdesc = $Lang::tr{'click to enable'};
    }

    #Colorize each line
    if ($settings{'KEY1'} eq $key) {
        print "<tr bgcolor='${Header::colouryellow}'>";
    } elsif ($key % 2) {
        print "<tr>";
        $col="bgcolor='$color{'color20'}'";
    } else {
        print "<tr>";
        $col="bgcolor='$color{'color22'}'";
    }
    print <<END;
<td align='center' $col>$temp[0]</td>
<td align='center' $col>$temp[1]</td>
<td align='center' $col>
<form method='post' action='$ENV{'SCRIPT_NAME'}'>
<input type='hidden' name='ACTION' value='$Lang::tr{'toggle enable disable'}' />
<input type='image' name='$Lang::tr{'toggle enable disable'}' src='/images/$gif' alt='$gdesc' title='$gdesc' />
<input type='hidden' name='KEY1' value='$key' />
</form>
</td>

<td align='center' $col>
<form method='post' action='$ENV{'SCRIPT_NAME'}'>
<input type='hidden' name='ACTION' value='$Lang::tr{'remove'}' />
<input type='image' name='$Lang::tr{'remove'}' src='/images/delete.gif' alt='$Lang::tr{'remove'}' title='$Lang::tr{'remove'}' />
<input type='hidden' name='KEY1' value='$key' />
</form>
</td>
</tr>
END

    $key++;
}
print "</table>";

# If table contains entries, print 'Key to action icons'
if ($key) {
print <<END;
<table>
<tr>
    <td class='boldbase'>&nbsp;<b>$Lang::tr{'legend'}:&nbsp;</b></td>
    <td><img src='/images/on.gif' alt='$Lang::tr{'click to disable'}' /></td>
    <td class='base'>$Lang::tr{'click to disable'}</td>
    <td>&nbsp;&nbsp;</td>
    <td><img src='/images/off.gif' alt='$Lang::tr{'click to enable'}' /></td>
    <td class='base'>$Lang::tr{'click to enable'}</td>
    <td>&nbsp;&nbsp;</td>
    <td><img src='/images/delete.gif' alt='$Lang::tr{'remove'}' /></td>
    <td class='base'>$Lang::tr{'remove'}</td>
</tr>
</table>
END
}

&Header::closebox();

&Header::closebigbox();

&Header::closepage();


## Ouf it's the end !

# Sort the "current" array according to choices
sub SortDataFile
{
    our %entries = ();

    # Sort pair of record received in $a $b special vars.
    # When IP is specified use numeric sort else alpha.
    # If sortname ends with 'Rev', do reverse sort.
    #
    sub fixedleasesort {
        my $qs='';             # The sort field specified minus 'Rev'
        if (rindex ($settings{'SORT_virtualIPLIST'},'Rev') != -1) {
            $qs=substr ($settings{'SORT_virtualIPLIST'},0,length($settings{'SORT_virtualIPLIST'})-3);
            if ($qs eq 'virtualIP') {
                my @a = split(/\./,$entries{$a}->{$qs});
                my @b = split(/\./,$entries{$b}->{$qs});
                ($b[0]<=>$a[0]) ||
                ($b[1]<=>$a[1]) ||
                ($b[2]<=>$a[2]) ||
                ($b[3]<=>$a[3]);
            } else {
                $entries{$b}->{$qs} cmp $entries{$a}->{$qs};
            }
        } else { #not reverse
            $qs=$settings{'SORT_virtualIPLIST'};
            if ($qs eq 'virtualIP') {
                my @a = split(/\./,$entries{$a}->{$qs});
                my @b = split(/\./,$entries{$b}->{$qs});
                ($a[0]<=>$b[0]) ||
                ($a[1]<=>$b[1]) ||
                ($a[2]<=>$b[2]) ||
                ($a[3]<=>$b[3]);
            } else {
                $entries{$a}->{$qs} cmp $entries{$b}->{$qs};
            }
        }
    }

    #Use an associative array (%entries)
    my $key = 0;
    foreach my $line (@current) {
        chomp( $line); #remove newline because can be on field 5 or 6 (addition of REMARK)
        my @temp = ( '','','', '');
        @temp = split (',',$line);

        # Build a pair 'Field Name',value for each of the data dataline.
        # Each SORTABLE field must have is pair.
        # Other data fields (non sortable) can be grouped in one

        my @record = ('KEY',$key++,'virtualIP',$temp[0],'interface',$temp[1]);
        my $record = {};                                # create a reference to empty hash
        %{$record} = @record;                           # populate that hash with @record
        $entries{$record->{KEY}} = $record;             # add this to a hash of hashes
    }

    open(FILE, ">$loxilbipfile") or die "$loxilbipfile open error";

    # Each field value is printed , with the newline ! Don't forget separator and order of them.
    foreach my $entry (sort fixedleasesort keys %entries) {
        print FILE "$entries{$entry}->{virtualIP},$entries{$entry}->{interface}\n";
    }

    close(FILE);
    # Reload sorted  @current
    open (FILE, "$loxilbipfile");
    @current = <FILE>;
    close (FILE);
}

sub manageIP {
    my ($action, %settings) = @_;

    # Initialize variables
    my @loxicmd_options;
    my $command = 'loxicmd';

    my $ip = $settings{'virtualIP'};
    my $interface = $settings{'interface'};

    push(@loxicmd_options, $action, "ip", $ip, $interface);

    #debug and display output in UI
    #my @output  = &General::system_output($command, @loxicmd_options);
    #$errormessage = join('', @output);
    &General::system($command, @loxicmd_options);

}

sub CreateIP {
    my (%settings) = @_;
    manageIP("create", %settings);
}

sub DeleteIP {
    my (%settings) = @_;
    manageIP("delete", %settings);
}
