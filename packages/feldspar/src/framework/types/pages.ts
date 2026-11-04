import { isInstanceOf } from '../helpers'
import { PromptFactory } from '../visualization/react/ui/prompts/factory'
import { PropsUIHeader } from './elements'
import { PropsUIPromptFileInput, PropsUIPromptProgress, PropsUIPromptConfirm, PropsUIPromptConsentForm, PropsUIPromptRadioInput } from './prompts'

export type PropsUIPage =
  PropsUIPageSplashScreen |
  PropsUIPageDataSubmission

export function isPropsUIPage (arg: any): arg is PropsUIPage {
  return (
    isPropsUIPageDataSubmission(arg)
  )
}

export interface PropsUIPageSplashScreen {
  __type__: 'PropsUIPageSplashScreen'
}

export interface PropsUIPageDataSubmission {
  __type__: 'PropsUIPageDataSubmission'
  platform: string
  header: PropsUIHeader
  body: (PropsUIPromptFileInput | PropsUIPromptProgress | PropsUIPromptConfirm | PropsUIPromptConsentForm | PropsUIPromptRadioInput)[]
  promptFactories?: PromptFactory[]
}
export function isPropsUIPageDataSubmission (arg: any): arg is PropsUIPageDataSubmission {
  return isInstanceOf<PropsUIPageDataSubmission>(arg, 'PropsUIPageDataSubmission', ['platform', 'header', 'body'])
}
