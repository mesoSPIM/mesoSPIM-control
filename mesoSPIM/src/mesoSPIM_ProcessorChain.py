"""
Processor Chain - Manages a chain of image processors that can be applied sequentially.
"""

import logging
import json
from pathlib import Path
from typing import Any, Dict, List, Optional
import numpy as np

from mesoSPIM.src.plugins.utils import get_image_processor_plugins, get_image_processor_class_from_name

logger = logging.getLogger(__name__)


class ProcessorChain:
    """
    Manages an ordered chain of image processors.
    
    Processors are applied in order from first to last when process() is called.
    Processors can be enabled/disabled individually without removing them from the chain.
    """
    
    def __init__(self):
        self._processors: List[Dict[str, Any]] = []
        self._load_available_processors()
    
    def _load_available_processors(self):
        """Load available processors from the plugin system."""
        self._available_processors = get_image_processor_plugins()
        logger.info(f"Loaded {len(self._available_processors)} available processors")
    
    @property
    def available_processors(self) -> List[Dict[str, Any]]:
        """Return list of available processors from plugins."""
        return self._available_processors
    
    @property
    def chain(self) -> List[Dict[str, Any]]:
        """Return the current processor chain configuration."""
        return self._processors.copy()
    
    @property
    def is_enabled(self) -> bool:
        """Return True if any processor in the chain is enabled."""
        return any(p['enabled'] for p in self._processors)
    
    def add_processor(self, name: str, enabled: bool = True) -> bool:
        """
        Add a processor to the chain by name.
        
        Args:
            name: Processor name
            enabled: Whether the processor should be enabled
            
        Returns:
            True if successful, False if processor not found
        """
        processor_class = get_image_processor_class_from_name(name)
        if processor_class is None:
            logger.warning(f"Processor not found: {name}")
            return False
        
        processor_instance = processor_class()
        
        self._processors.append({
            'name': name,
            'enabled': enabled,
            'instance': processor_instance,
        })
        logger.info(f"Added processor to chain: {name}")
        return True
    
    def remove_processor(self, index: int) -> bool:
        """
        Remove a processor from the chain by index.
        
        Args:
            index: Index in the chain
            
        Returns:
            True if successful, False if index out of range
        """
        if 0 <= index < len(self._processors):
            removed = self._processors.pop(index)
            logger.info(f"Removed processor from chain: {removed['name']}")
            return True
        return False
    
    def remove_processor_by_name(self, name: str) -> bool:
        """
        Remove a processor from the chain by name (removes first occurrence).
        
        Args:
            name: Processor name
            
        Returns:
            True if successful, False if not found
        """
        for i, p in enumerate(self._processors):
            if p['name'] == name:
                return self.remove_processor(i)
        return False
    
    def enable_processor(self, index: int) -> bool:
        """
        Enable a processor in the chain.
        
        Args:
            index: Index in the chain
            
        Returns:
            True if successful, False if index out of range
        """
        if 0 <= index < len(self._processors):
            self._processors[index]['enabled'] = True
            return True
        return False
    
    def disable_processor(self, index: int) -> bool:
        """
        Disable a processor in the chain.
        
        Args:
            index: Index in the chain
            
        Returns:
            True if successful, False if index out of range
        """
        if 0 <= index < len(self._processors):
            self._processors[index]['enabled'] = False
            return True
        return False
    
    def move_processor(self, from_index: int, to_index: int) -> bool:
        """
        Move a processor from one position to another.
        
        Args:
            from_index: Current position
            to_index: Target position
            
        Returns:
            True if successful, False if indices out of range
        """
        if not (0 <= from_index < len(self._processors) and 0 <= to_index < len(self._processors)):
            return False
        
        processor = self._processors.pop(from_index)
        self._processors.insert(to_index, processor)
        return True
    
    def reorder(self, new_order: List[int]) -> bool:
        """
        Reorder the chain using a list of indices.
        
        Args:
            new_order: List of indices specifying the new order
            
        Returns:
            True if successful, False if invalid order
        """
        if len(new_order) != len(self._processors):
            return False
        if set(new_order) != set(range(len(self._processors))):
            return False
        
        self._processors = [self._processors[i] for i in new_order]
        return True
    
    def configure_processor(self, index: int, params: Dict[str, Any]) -> bool:
        """
        Configure a processor with new parameters.
        
        Args:
            index: Index in the chain
            params: Configuration parameters
            
        Returns:
            True if successful, False if index out of range
        """
        if 0 <= index < len(self._processors):
            self._processors[index]['instance'].configure(params)
            return True
        return False
    
    def get_processor_config(self, index: int) -> Optional[Dict[str, Any]]:
        """
        Get configuration of a processor.
        
        Args:
            index: Index in the chain
            
        Returns:
            Configuration dict or None if index out of range
        """
        if 0 <= index < len(self._processors):
            return self._processors[index]['instance'].get_config()
        return None
    
    def reset(self):
        """Reset all processors (useful for starting a new acquisition)."""
        for p in self._processors:
            p['instance'].reset()
    
    def clear(self):
        """Remove all processors from the chain."""
        self._processors.clear()
    
    def process(self, image: np.ndarray) -> np.ndarray:
        """
        Process an image through the enabled processors in sequence.
        
        Args:
            image: Input image array
            
        Returns:
            Processed image array
        """
        if not self.is_enabled:
            return image
        
        result = image
        for p in self._processors:
            if p['enabled']:
                try:
                    result = p['instance'].process_frame(result)
                except Exception as e:
                    logger.error(f"Error in processor {p['name']}: {e}")
        return result
    
    def get_config(self) -> Dict[str, Any]:
        """
        Get the current chain configuration.
        
        Returns:
            Dict with chain configuration
        """
        return {
            'processors': [
                {
                    'name': p['name'],
                    'enabled': p['enabled'],
                    'config': p['instance'].get_config(),
                }
                for p in self._processors
            ]
        }
    
    def set_config(self, config: Dict[str, Any]):
        """
        Set the chain configuration.
        
        Args:
            config: Dict with chain configuration
        """
        self.clear()
        
        if 'processors' not in config:
            return
        
        for p_config in config['processors']:
            name = p_config.get('name')
            enabled = p_config.get('enabled', True)
            proc_config = p_config.get('config', {})
            
            if self.add_processor(name, enabled):
                if proc_config:
                    idx = len(self._processors) - 1
                    self.configure_processor(idx, proc_config)

    def save_to_file(self, filepath: str) -> bool:
        """
        Save the processor chain configuration to a JSON file.
        
        Args:
            filepath: Path to the JSON file
            
        Returns:
            True if successful, False otherwise
        """
        try:
            config = self.get_config()
            path = Path(filepath)
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, 'w') as f:
                json.dump(config, f, indent=2)
            logger.info(f"Processor chain configuration saved to {filepath}")
            return True
        except Exception as e:
            logger.error(f"Failed to save processor chain config to {filepath}: {e}")
            return False

    @classmethod
    def load_from_file(cls, filepath: str) -> Dict[str, Any]:
        """
        Load a processor chain configuration from a JSON file.
        
        Args:
            filepath: Path to the JSON file
            
        Returns:
            Dict with chain configuration, or empty dict if file doesn't exist
        """
        try:
            path = Path(filepath)
            if not path.exists():
                logger.info(f"Processor chain config file not found: {filepath}")
                return {}
            with open(path, 'r') as f:
                config = json.load(f)
            logger.info(f"Processor chain configuration loaded from {filepath}")
            return config
        except Exception as e:
            logger.error(f"Failed to load processor chain config from {filepath}: {e}")
            return {}
