# post notice if not Raspbian 10 or newer
unless ($facts['os']['name'] == 'Debian') and
  ($facts['os']['distro']['id'] == 'Raspbian') and
  (versioncmp($facts['os']['release']['major'], '10') == 0) {
  notice('This manifest has only been tested Raspbian 10 (buster)')
}

$main_packages = [
  'git',
  'libgl1-mesa-dri',
  'lightdm',
  'tmux',
  'x11-xserver-utils',
  'xserver-xorg',
  'vim',
]

$piweatherrock_packages = [
  'libjpeg-dev',
  'libportmidi-dev',
  'libsdl1.2-dev',
  'libsdl-image1.2-dev',
  'libsdl-mixer1.2-dev',
  'libsdl-ttf2.0-dev',
  'libtimedate-perl',
  'python3-pip',
]

package { [ $main_packages, $piweatherrock_packages, ]:
  ensure          => latest,
  install_options => [
    '--no-install-recommends',
  ],
}

unless $facts['os']['hardware'] == 'x86_64' {
  $non_x86_packages = [ 'realvnc-vnc-server', ]
  package { $non_x86_packages:
    ensure          => latest,
    install_options => [
      '--no-install-recommends',
    ],
  }

  service { 'vncserver-x11-serviced':
    ensure  => running,
    enable  => true,
    require => Package['realvnc-vnc-server'],
  }
}

# if using Raspbian Lite uncomment the bit below for a minimal desktop and terminal
# package { [ 'awesome', 'lxterminal', ]:
#   ensure          => latest,
#   install_options => [
#     '--no-install-recommends',
#   ],
#   before          => Python::Requirements['/home/pi/PiWeatherRock/requirements.txt'],
# }

# allow all sessions to share the X server
# see https://www.computerhope.com/unix/xhost.htm
file {
  default:
    owner => 'pi',
    group => 'pi',
    mode  => '0755',
  ;
  '/home/pi/bin':
    ensure => directory,
  ;
  '/home/pi/bin/xhost.sh':
    ensure  => file,
    content => @(END),
      #!/bin/bash
      xhost +
      | END
  ;
}

# make lightdm use the xhost settings above
exec { 'enable display-setup-script':
  path    => '/bin:/usr/bin',
  command => "sed -i 's|#display-setup-script=|display-setup-script=/home/pi/bin/xhost.sh|' /etc/lightdm/lightdm.conf",
  unless  => "grep -e '^display-setup-script' /etc/lightdm/lightdm.conf",
}

vcsrepo { '/home/pi/PiWeatherRock':
  ensure   => latest,
  provider => git,
  source   => 'https://github.com/genebean/PiWeatherRock.git',
}

$python_packages = [
  'darkskylib',
  'pygame',
  'pyserial',
  'requests',
]

python::pip { $python_packages:
  pip_provider => 'pip3',
  require      => Package[ $main_packages, $piweatherrock_packages, ],
}

systemd::unit_file { 'PiWeatherRock.service':
  source  => 'file:///home/pi/PiWeatherRock/PiWeatherRock.service',
  require => Python::Pip[$python_packages],
  notify  => Service['PiWeatherRock.service'],
}

service {'PiWeatherRock.service':
  ensure    => running,
  enable    => true,
  require   => Systemd::Unit_file['PiWeatherRock.service'],
  subscribe => [
    Exec['enable display-setup-script'],
    File['/home/pi/bin/xhost.sh'],
    Python::Pip[$python_packages],
    Vcsrepo['/home/pi/PiWeatherRock'],
  ],
}
