<?php
// Router for `php -S` that mimics DokuWiki's .htaccess rewrite rules (userewrite=1).
//   php -S 127.0.0.1:8090 -t /var/www/dokuwiki dw-router.php
$root = '/var/www/dokuwiki';
$path = rawurldecode(parse_url($_SERVER['REQUEST_URI'], PHP_URL_PATH));
chdir($root);
if ($path !== '/' && is_file($root . $path) && !str_ends_with($path, '.php')) return false;
if ($path !== '/' && is_file($root . $path)) { $_SERVER['SCRIPT_NAME'] = $path; require $root . $path; return true; }
if (preg_match('#^/_media/(.*)$#', $path, $m)) { $_GET['media'] = $_REQUEST['media'] = $m[1]; $_SERVER['SCRIPT_NAME'] = '/lib/exe/fetch.php'; require 'lib/exe/fetch.php'; return true; }
if (preg_match('#^/_detail/(.*)$#', $path, $m)) { $_GET['media'] = $_REQUEST['media'] = $m[1]; $_SERVER['SCRIPT_NAME'] = '/lib/exe/detail.php'; require 'lib/exe/detail.php'; return true; }
$id = trim($path, '/');
if ($id !== '') { $_GET['id'] = $_REQUEST['id'] = $id; }
$_SERVER['SCRIPT_NAME'] = '/doku.php';
require 'doku.php';
