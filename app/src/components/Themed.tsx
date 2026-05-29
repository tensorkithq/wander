/**
 * Learn more about Light and Dark modes:
 * https://docs.expo.io/guides/color-schemes/
 */

import { Text as DefaultText, View as DefaultView } from 'react-native';

export type TextProps = DefaultText['props'];
export type ViewProps = DefaultView['props'];

export function Text(props: TextProps) {
  const { className, ...otherProps } = props;
  return (
    <DefaultText
      className={`text-black dark:text-white ${className ?? ''}`}
      {...otherProps}
    />
  );
}

export function View(props: ViewProps) {
  const { className, ...otherProps } = props;
  return (
    <DefaultView
      className={`bg-white dark:bg-black ${className ?? ''}`}
      {...otherProps}
    />
  );
}
