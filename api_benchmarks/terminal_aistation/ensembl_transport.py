"""Keep VEP release/115 dependencies, obtain version SHA via Git instead of rate-limited REST."""
import shlex
import base64

PATCH = r'''from pathlib import Path
p = Path('/app/data/ensembl-vep-release-115/INSTALL.pl')
s = p.read_text()
a = s.index('sub get_module_sub_version {')
z = s.index('\nsub get_vep_sub_version {', a)
replacement = r"""sub get_module_sub_version {
  my $module = shift;
  die "Unexpected Ensembl module" unless $module =~ /^ensembl(?:-(?:variation|funcgen|compara|io))?$/;
  my $branch = looks_like_number($API_VERSION) ? 'release/'.$API_VERSION : $API_VERSION;
  open(my $git, '-|', 'git', '-c', 'http.version=HTTP/1.1', 'ls-remote', '--heads',
       "https://github.com/Ensembl/$module.git", "refs/heads/$branch") or die "Cannot read Git ref: $!";
  my $line = <$git>;
  close($git) or die "Git ref lookup failed";
  die "Invalid Git ref response" unless defined($line) && $line =~ /^([0-9a-f]{40})\s/;
  return $1;
}
"""
p.write_text(s[:a] + replacement + s[z:])
'''


def adapt(source):
    marker = 'RUN cd /app/data/ensembl-vep-release-115 && \\\n'
    if 'perl INSTALL.pl --AUTO a --NO_HTSLIB --NO_TEST --NO_UPDATE' not in source:
        return source, False
    if source.count(marker) != 1:
        raise ValueError('Unexpected VEP installer layout; cannot apply transport adaptation')
    return source.replace(marker, 'RUN python3 -c ' + shlex.quote('import base64;exec(base64.b64decode(' + repr(base64.b64encode(PATCH.encode()).decode()) + '))') + '\n' + marker), True
