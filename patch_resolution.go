package main

import (
	"bufio"
	"bytes"
	"encoding/binary"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
)

const (
	exeName      = "HUNDRED_LINE.exe"
	backupName   = "HUNDRED_LINE.exe.backup"
	configName   = "userconfig.properties"
	configBackup = "userconfig.properties.backup"

	targetWidth  = 5120
	targetHeight = 2880

	origWidth  = 3840
	origHeight = 2160

	// Offsets in the executable
	tableOffset        = 0xBDA4F0
	widthGetterOffset  = 0x054DF7
	widthParamOffset   = 0x4B4305
	heightGetterOffset = 0x054D37
	heightParamOffset  = 0x4B430B
)

type Patch struct {
	Offset      int
	Original    []byte
	Replacement []byte
	Description string
}

func main() {
	fmt.Println("╔════════════════════════════════════════════════════════════╗")
	fmt.Println("║     The Hundred Line - Resolution Patcher                  ║")
	fmt.Println("║     Patches 3840x2160 → 5120x2880 (5K)                     ║")
	fmt.Println("╚════════════════════════════════════════════════════════════╝")
	fmt.Println()

	// Check if exe exists
	if _, err := os.Stat(exeName); os.IsNotExist(err) {
		fmt.Printf("ERROR: %s not found!\n", exeName)
		fmt.Println("Please place this patcher in the same folder as the game executable.")
		waitForExit()
		return
	}

	// Read the executable to check if patched
	data, err := os.ReadFile(exeName)
	if err != nil {
		fmt.Printf("ERROR: Failed to read %s: %v\n", exeName, err)
		waitForExit()
		return
	}

	if isPatched(data) {
		runRestoreMode()
	} else {
		runPatchMode(data)
	}
}

func isPatched(data []byte) bool {
	newWidthBytes := make([]byte, 4)
	binary.LittleEndian.PutUint32(newWidthBytes, targetWidth)

	// Check if the resolution table has the patched value
	if len(data) > tableOffset+4 {
		return bytes.Equal(data[tableOffset:tableOffset+4], newWidthBytes)
	}
	return false
}

func runPatchMode(data []byte) {
	fmt.Println("Mode: PATCH")
	fmt.Println()
	fmt.Printf("This will patch %s to support 5120x2880 resolution.\n", exeName)
	fmt.Println("A backup will be created automatically.")
	fmt.Println()

	fmt.Printf("File size: %d bytes\n", len(data))
	fmt.Println()

	// Create patches
	patches := createPatches(data)
	if len(patches) == 0 {
		fmt.Println("ERROR: No valid patch locations found.")
		fmt.Println("The executable may be a different version.")
		waitForExit()
		return
	}

	// Display patches
	fmt.Println("The following changes will be made:")
	fmt.Println("────────────────────────────────────────────────────────────")
	for _, p := range patches {
		origVal := binary.LittleEndian.Uint32(p.Original)
		newVal := binary.LittleEndian.Uint32(p.Replacement)
		fmt.Printf("  0x%08X: %d → %d\n", p.Offset, origVal, newVal)
		fmt.Printf("              %s\n", p.Description)
	}
	fmt.Println("────────────────────────────────────────────────────────────")
	fmt.Printf("Total patches: %d\n", len(patches))
	fmt.Println()
	fmt.Println("userconfig.properties will also be updated.")
	fmt.Println()

	// Wait for confirmation
	fmt.Println("Press ENTER to apply the patch, or close this window to cancel...")
	waitForEnter()

	// Create backup
	fmt.Printf("Creating backup: %s\n", backupName)
	if err := os.WriteFile(backupName, data, 0644); err != nil {
		fmt.Printf("ERROR: Failed to create backup: %v\n", err)
		waitForExit()
		return
	}

	// Apply patches
	patchedData := make([]byte, len(data))
	copy(patchedData, data)

	for _, p := range patches {
		copy(patchedData[p.Offset:], p.Replacement)
	}

	// Write patched executable
	if err := os.WriteFile(exeName, patchedData, 0644); err != nil {
		fmt.Printf("ERROR: Failed to write patched file: %v\n", err)
		waitForExit()
		return
	}

	// Update userconfig.properties
	if err := patchUserConfig(); err != nil {
		fmt.Printf("WARNING: Failed to update %s: %v\n", configName, err)
		fmt.Println("You may need to manually set the resolution in the config file.")
	} else {
		fmt.Printf("Updated %s\n", configName)
	}

	fmt.Println()
	fmt.Println("╔════════════════════════════════════════════════════════════╗")
	fmt.Println("║                    PATCH SUCCESSFUL!                       ║")
	fmt.Println("╚════════════════════════════════════════════════════════════╝")
	fmt.Println()
	fmt.Println("Run this patcher again to restore the original executable.")
	fmt.Println()
	waitForExit()
}

func runRestoreMode() {
	fmt.Println("Mode: RESTORE")
	fmt.Println()
	fmt.Println("The executable appears to be patched.")
	fmt.Println("This will restore the original unpatched executable.")
	fmt.Println()

	// Check if backup exists
	if _, err := os.Stat(backupName); os.IsNotExist(err) {
		fmt.Printf("ERROR: Backup file not found: %s\n", backupName)
		fmt.Println("Cannot restore without backup.")
		waitForExit()
		return
	}

	// Verify backup is readable
	backupData, err := os.ReadFile(backupName)
	if err != nil {
		fmt.Printf("ERROR: Failed to read backup: %v\n", err)
		waitForExit()
		return
	}

	fmt.Printf("Backup size: %d bytes\n", len(backupData))
	fmt.Println()

	// Wait for confirmation
	fmt.Println("Press ENTER to restore the original executable, or close this window to cancel...")
	waitForEnter()

	// Restore from backup
	if err := os.WriteFile(exeName, backupData, 0644); err != nil {
		fmt.Printf("ERROR: Failed to restore executable: %v\n", err)
		waitForExit()
		return
	}

	// Remove exe backup
	if err := os.Remove(backupName); err != nil {
		fmt.Printf("WARNING: Failed to remove backup file: %v\n", err)
	}

	// Restore userconfig.properties if backup exists
	if err := restoreUserConfig(); err != nil {
		fmt.Printf("WARNING: Failed to restore %s: %v\n", configName, err)
	} else {
		fmt.Printf("Restored %s\n", configName)
	}

	fmt.Println()
	fmt.Println("╔════════════════════════════════════════════════════════════╗")
	fmt.Println("║                   RESTORE SUCCESSFUL!                      ║")
	fmt.Println("╚════════════════════════════════════════════════════════════╝")
	fmt.Println()
	fmt.Println("The original executable has been restored.")
	fmt.Println()
	waitForExit()
}

func patchUserConfig() error {
	// Read existing config
	configData, err := os.ReadFile(configName)
	if err != nil {
		return fmt.Errorf("failed to read config: %w", err)
	}

	// Parse JSON
	var config map[string]interface{}
	if err := json.Unmarshal(configData, &config); err != nil {
		return fmt.Errorf("failed to parse config: %w", err)
	}

	// Backup original config (only if backup doesn't exist)
	if _, err := os.Stat(configBackup); os.IsNotExist(err) {
		if err := os.WriteFile(configBackup, configData, 0644); err != nil {
			return fmt.Errorf("failed to create config backup: %w", err)
		}
		fmt.Printf("Created config backup: %s\n", configBackup)
	}

	// Update values (preserving X and Y)
	config["App.Window.W"] = targetWidth
	config["App.Window.H"] = targetHeight
	config["App.Window.Mode"] = "BorderlessWindowed"

	// Write updated config with indentation
	updatedData, err := json.MarshalIndent(config, "", "\t")
	if err != nil {
		return fmt.Errorf("failed to encode config: %w", err)
	}

	if err := os.WriteFile(configName, updatedData, 0644); err != nil {
		return fmt.Errorf("failed to write config: %w", err)
	}

	return nil
}

func restoreUserConfig() error {
	// Check if config backup exists
	if _, err := os.Stat(configBackup); os.IsNotExist(err) {
		return nil // No backup to restore, not an error
	}

	// Read backup
	backupData, err := os.ReadFile(configBackup)
	if err != nil {
		return fmt.Errorf("failed to read config backup: %w", err)
	}

	// Restore config
	if err := os.WriteFile(configName, backupData, 0644); err != nil {
		return fmt.Errorf("failed to restore config: %w", err)
	}

	// Remove config backup
	if err := os.Remove(configBackup); err != nil {
		fmt.Printf("WARNING: Failed to remove config backup: %v\n", err)
	}

	return nil
}

func createPatches(data []byte) []Patch {
	var patches []Patch

	origWidthBytes := make([]byte, 4)
	origHeightBytes := make([]byte, 4)
	newWidthBytes := make([]byte, 4)
	newHeightBytes := make([]byte, 4)

	binary.LittleEndian.PutUint32(origWidthBytes, origWidth)
	binary.LittleEndian.PutUint32(origHeightBytes, origHeight)
	binary.LittleEndian.PutUint32(newWidthBytes, targetWidth)
	binary.LittleEndian.PutUint32(newHeightBytes, targetHeight)

	// Resolution table patches
	if len(data) > tableOffset+8 {
		if bytes.Equal(data[tableOffset:tableOffset+4], origWidthBytes) {
			patches = append(patches, Patch{
				Offset:      tableOffset,
				Original:    origWidthBytes,
				Replacement: newWidthBytes,
				Description: fmt.Sprintf("Resolution table: %d → %d (width)", origWidth, targetWidth),
			})
		}
		if bytes.Equal(data[tableOffset+4:tableOffset+8], origHeightBytes) {
			patches = append(patches, Patch{
				Offset:      tableOffset + 4,
				Original:    origHeightBytes,
				Replacement: newHeightBytes,
				Description: fmt.Sprintf("Resolution table: %d → %d (height)", origHeight, targetHeight),
			})
		}
	}

	// Code patches
	codePatches := []struct {
		offset      int
		original    []byte
		replacement []byte
		description string
	}{
		{widthGetterOffset, origWidthBytes, newWidthBytes, "Width getter (mov eax, 3840)"},
		{widthParamOffset, origWidthBytes, newWidthBytes, "Resolution param width (mov edx, 3840)"},
		{heightGetterOffset, origHeightBytes, newHeightBytes, "Height getter (mov eax, 2160)"},
		{heightParamOffset, origHeightBytes, newHeightBytes, "Resolution param height (mov r8d, 2160)"},
	}

	for _, cp := range codePatches {
		if len(data) > cp.offset+4 && bytes.Equal(data[cp.offset:cp.offset+4], cp.original) {
			patches = append(patches, Patch{
				Offset:      cp.offset,
				Original:    cp.original,
				Replacement: cp.replacement,
				Description: cp.description,
			})
		} else {
			fmt.Printf("WARNING: Mismatch at 0x%X, skipping: %s\n", cp.offset, cp.description)
		}
	}

	return patches
}

func waitForEnter() {
	reader := bufio.NewReader(os.Stdin)
	reader.ReadString('\n')
}

func waitForExit() {
	fmt.Println("Press ENTER to exit...")
	waitForEnter()
}

func init() {
	// Change to the directory where the executable is located
	exe, err := os.Executable()
	if err == nil {
		dir := filepath.Dir(exe)
		os.Chdir(dir)
	}
}
