# processing/image_processor.py
import numpy as np
import cv2
from PyQt5.QtCore import QThread, pyqtSignal

class ImageProcessor(QThread):
    progress = pyqtSignal(int)
    result = pyqtSignal(np.ndarray)

    def __init__(self, images, components, region, weights, region_size):
        super().__init__()
        self.images = images
        self.components = components
        self.region = region
        self.weights = weights
        self.region_size = region_size
        self.running = True

    def run(self):
        try:
            ft_components = []
            target_shape = None

            # Determine target dimensions
            for image in self.images:
                if image is not None:
                    target_shape = image.shape
                    break

            if target_shape is None:
                raise ValueError("No valid images provided for processing.")

            print(f"Target shape for resizing: {target_shape}")

            for i, image in enumerate(self.images):
                if not self.running:
                    return
                if image is None:
                    print(f"Image {i + 1} is None, skipping.")
                    continue

                try:
                    resized_image = cv2.resize(image, (target_shape[1], target_shape[0]))
                    print(f"Image {i + 1} resized to {resized_image.shape}")
                    
                    fft = np.fft.fft2(resized_image)
                    fft_shift = np.fft.fftshift(fft)
                    print(f"Image {i + 1} FFT computed")

                    magnitude = np.abs(fft_shift)
                    phase = np.angle(fft_shift)
                    real = np.real(fft_shift)
                    imaginary = np.imag(fft_shift)

                    ft_components.append({
                        "Magnitude": magnitude,
                        "Phase": phase,
                        "Real": real,
                        "Imaginary": imaginary
                    })

                    print(f"Processed image {i + 1}/{len(self.images)}: Component shapes - Magnitude: {magnitude.shape}, Phase: {phase.shape}")

                    self.progress.emit((i + 1) * 100 // len(self.images))
                except Exception as e:
                    print(f"Error processing image {i + 1}: {e}")
                    continue

            if not ft_components:
                print("No valid FT components available for mixing.")
                return

            mixed_ft = None
            for i, weight in enumerate(self.weights):
                component_type = self.components[i]
                component_data = ft_components[i]
                print(f"Selected component for viewer {i}: {component_type}")

                try:
                    # Reconstruct the complex FT based on the selected component type
                    if component_type == "FT Magnitude":
                        selected_magnitude = component_data["Magnitude"]
                        selected_phase = component_data["Phase"]
                        complex_ft = selected_magnitude * np.exp(1j * selected_phase)
                    elif component_type == "FT Phase":
                        selected_magnitude = component_data["Magnitude"]
                        selected_phase = component_data["Phase"]
                        complex_ft = selected_magnitude * np.exp(1j * selected_phase)
                    elif component_type == "FT Real":
                        selected_real = component_data["Real"]
                        selected_imaginary = component_data["Imaginary"]
                        complex_ft = selected_real + 1j * selected_imaginary
                    elif component_type == "FT Imaginary":
                        selected_real = component_data["Real"]
                        selected_imaginary = component_data["Imaginary"]
                        complex_ft = selected_real + 1j * selected_imaginary
                    else:
                        print(f"Unknown component: {component_type}")
                        continue

                    # Apply region selection (inner or outer)
                    complex_ft = self.apply_region(complex_ft, self.region_size, region_type=self.region.lower())

                    # Apply weight and combine
                    weighted_ft = weight * complex_ft
                    if mixed_ft is None:
                        mixed_ft = weighted_ft
                    else:
                        mixed_ft += weighted_ft

                except Exception as e:
                    print(f"Error combining FT components for viewer {i}: {e}")
                    continue

            if mixed_ft is None:
                print("No valid FT components were mixed.")
                return

            # Apply inverse FFT to get the result
            try:
                mixed_image = np.fft.ifft2(np.fft.ifftshift(mixed_ft)).real
                mixed_image = np.clip(mixed_image, 0, 255).astype(np.uint8)  # Ensure valid range
                self.result.emit(mixed_image)
                print("Final mixed image generated successfully.")
            except Exception as e:
                print(f"Error performing IFFT: {e}")
                empty_image = np.zeros(target_shape, dtype=np.uint8)
                self.result.emit(empty_image)

            self.progress.emit(100)
        except Exception as e:
            print(f"Error during image processing: {e}")
            empty_image = np.zeros(target_shape if target_shape else (1, 1), dtype=np.uint8)
            self.result.emit(empty_image)
            self.progress.emit(100)

    def apply_region(self, complex_ft, region_size_percentage, region_type='inner'):
        """Apply region selection to the complex FT based on the region type and size."""
        try:
            h, w = complex_ft.shape
            region_size = int(min(h, w) * region_size_percentage / 100)
            mask = np.ones((h, w), dtype=bool)

            if region_type == 'inner':
                mask[:(h - region_size) // 2, :] = 0
                mask[(h + region_size) // 2:, :] = 0
                mask[:, :(w - region_size) // 2] = 0
                mask[:, (w + region_size) // 2:] = 0
            else:  # 'outer'
                mask[(h - region_size) // 2:(h + region_size) // 2, :] = 0
                mask[:, (w - region_size) // 2:(w + region_size) // 2] = 0

            print(f"Applied {region_type} region mask with size percentage: {region_size_percentage}%")
            return complex_ft * mask
        except Exception as e:
            print(f"Error applying region mask: {e}")
            return complex_ft