//go:build !linux

package main

// No weaker approximation of the Linux ownership handshake is advertised.
func installOwnership(expectedParent int) bool { return false }
